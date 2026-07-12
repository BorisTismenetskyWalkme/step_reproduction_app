import base64
import os
import re
import time

import requests
from flask import Flask, request, render_template_string, send_file

app = Flask(__name__)

# App version
APP_VERSION = "3.3"

# Fill your credentials manually here or prompt internally
BS_USERNAME = os.environ.get("AUTOMATION_BS_USER", "")
BS_ACCESS_KEY = os.environ.get("AUTOMATION_BS_PASS", "")

if not BS_USERNAME or not BS_ACCESS_KEY:
    print("WARNING: BrowserStack credentials not set in environment variables.")
    print("Set AUTOMATION_BS_USER and AUTOMATION_BS_PASS environment variables.")
    print("The app will try to use auth_token from the session URL if available.")


def get_bs_build_hashed_id(build_name_or_hash):
    """Convert build name to hashed build ID using BrowserStack API.
    
    This function returns only the FIRST matching build for backward compatibility.
    Use get_all_hashed_build_ids() to get all matches.

    Args:
        build_name_or_hash: Build name like "20260412-064121-6903a" 
                           OR hashed_id like "910d848cde11c50835c0537c3b8899552067f48c"

    Returns:
        First hashed build ID string

    Raises:
        ValueError if build not found or API error
    """
    # Use the new function to get all matches
    all_hashed_ids = get_all_hashed_build_ids(build_name_or_hash)

    # If multiple matches found, warn the user
    if len(all_hashed_ids) > 1:
        print(f"\n{'=' * 80}")
        print(f"⚠️  WARNING: Found {len(all_hashed_ids)} builds with name '{build_name_or_hash}'")
        print(f"{'=' * 80}")
        print(f"Returning the FIRST match: {all_hashed_ids[0]}")
        print(f"\n💡 TIP: Use the hashed_id directly for precise targeting!")
        print(f"   Or use get_all_hashed_build_ids() to get all matches.")
        print(f"{'=' * 80}\n")

    return all_hashed_ids[0]


# GUID to EUX BO email mapping
GUID_TO_EMAIL_MAPPING = {
    "0f949935b22247c8a91bcad78e10190a": "qa_automation_default_ywlp@walkme.com",
    "46d76a2b9cde4b6d9316004b563efc40": "qa_automation_workday_s5l0@walkme.com",
    "c1b8bed522bf41d9a8ea2b8515b23cd9": "qa_automation_unknown_4325@walkme.com",
    "81558d37bba7475b8d1dd550825f1b18": "qa_automation_unknown_c3b3@walkme.com",
    "6d96e7ce05754444967448e39986c979": "qa_automation_unknown_cbae@walkme.com",
    "5f439cf758f44ce79748145daacb6f35": "qa_automation_dynamics_b120@walkme.com",
    "9fae8c3898ff4abab18b8de79da07cfb": "qa_automation_lightning_8bb7@walkme.com",
    "036294f3a135470ebdef8d75d5729ac3": "qa_automation_salesforceli_822c@walkme.com",
    "fbe70bc109224c1d90da85900e7687dc": "qa_automation_successfacto_6fb4@walkme.com",
    "6b7adfb602a34c2681c83e27139d3e25": "qa_automation_oraclecloud_8654@walkme.com",
    "d53165f4dc614a9b915847e272ac53d9": "qa_automation_ariba_8b12@walkme.com",
    "420e7292e1e944af8274aafaa74a4434": "qa_automation_unknown_7abc@walkme.com",
    "e46f14e1f77d4f02bb3be1f20dba31dc": "qa_automation_servicenow_d993@walkme.com",
    "4823e284a4fd4ab19f49cdfeb6630f76": "qa_automation_lightning_521e@walkme.com",
    "e4c02787c1a845c886757633064bf50d": "qa_automation_concur_0bff@walkme.com",
    "8e4153c1579445e49d3a47a6af90bcf4": "qa_automation_unknown_f288@walkme.com",
    "e6d9a405120d42e0904514a0ad3e912d": "qa_automation_successfacto_3ab3@walkme.com",
    "cd402ac3721e4fd3b06a357247fa22e8": "qa_automation_successfacto_d90e@walkme.com",
    "a5e4b07a4e15415e90d738c6909c6091": "qa_automation_successfacto_4ccf@walkme.com",
    "d674d156fa1a443ba23986b309227eac": "sapautomation_successfacto_509a@walkme.com",
    "6a48f12bce5a4b1497f3d5905c5f25e8": "sapautomation_concur_756c@walkme.com",
    "93c2b84bf8d141e58566769658133ffd": "sapautomation_concur_5059@walkme.com",
    "7a50330389c847e28b25418732ce9bf8": "sapautomation_successfacto_6647@walkme.com"
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Test Reproduction - {{ test_name }}</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { 
    height: 100%;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background: #1a202c;
    color: #e2e8f0;
}

/* Main layout */
.app-container {
    display: flex;
    flex-direction: column;
    height: 100vh;
}

/* Header */
.header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 12px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
}
.header-left {
    display: flex;
    align-items: center;
    gap: 16px;
    min-width: 150px;
}
.header-center {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
    justify-content: center;
}
.header h1 {
    font-size: 18px;
    font-weight: 600;
    color: white;
}
.header .app-name {
    font-size: 16px;
    font-weight: 600;
    color: white;
}
.header .test-name-label {
    font-size: 14px;
    color: rgba(255,255,255,0.85);
}
.header .test-name {
    font-size: 14px;
    color: rgba(255,255,255,0.85);
    background: rgba(255,255,255,0.15);
    padding: 6px 12px;
    border-radius: 6px;
    max-width: 500px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.header-right {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 13px;
    color: rgba(255,255,255,0.9);
}
.status-badge {
    padding: 4px 10px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
}
.status-passed { background: #38a169; color: white; }
.status-failed { background: #e53e3e; color: white; }
.status-unknown { background: #d69e2e; color: white; }

/* Main content - two panels */
.main-content {
    display: flex;
    flex: 1;
    overflow: hidden;
}

/* Left panel - Video */
.video-panel {
    width: 55%;
    background: #2d3748;
    display: flex;
    flex-direction: column;
    border-right: 1px solid #4a5568;
}
.video-header {
    padding: 12px 16px;
    background: #2d3748;
    border-bottom: 1px solid #4a5568;
    font-size: 14px;
    font-weight: 600;
    color: #a0aec0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.video-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    background: #1a202c;
    position: relative;
}
.video-container video {
    width: 100%;
    max-height: 100%;
    border-radius: 8px;
    background: #000;
}
.speed-controls {
    position: absolute;
    bottom: 24px;
    right: 24px;
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(0, 0, 0, 0.7);
    padding: 6px 10px;
    border-radius: 6px;
    z-index: 10;
}
.speed-controls span {
    font-size: 11px;
    color: #a0aec0;
    margin-right: 4px;
}
.speed-btn {
    padding: 4px 10px;
    border: 1px solid #4a5568;
    background: #2d3748;
    color: #a0aec0;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}
.speed-btn:hover {
    background: #4a5568;
    color: #e2e8f0;
}
.speed-btn.active {
    background: #667eea;
    border-color: #667eea;
    color: white;
}
}
.video-fallback {
    text-align: center;
    color: #a0aec0;
}
.video-fallback a {
    display: inline-block;
    background: #667eea;
    color: white;
    padding: 12px 24px;
    border-radius: 8px;
    text-decoration: none;
    font-weight: 500;
    margin-top: 12px;
}

/* Right panel - Steps */
.steps-panel {
    width: 45%;
    display: flex;
    flex-direction: column;
    background: #2d3748;
    position: relative;
}
.steps-header {
    padding: 12px 16px;
    background: #2d3748;
    border-bottom: 1px solid #4a5568;
    font-size: 14px;
    font-weight: 600;
    color: #a0aec0;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.steps-count {
    background: #667eea;
    color: white;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 12px;
}
.steps-container {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
}

/* Steps list */
.steps-list {
    list-style: none;
    counter-reset: step-counter;
}
.step-item {
    display: flex;
    align-items: flex-start;
    padding: 12px 14px;
    margin-bottom: 8px;
    background: #3d4a5c;
    border-radius: 8px;
    transition: all 0.2s ease;
    counter-increment: step-counter;
    border-left: 3px solid transparent;
}
.step-item:hover {
    background: #4a5a6e;
    border-left-color: #667eea;
}
.step-item::before {
    content: counter(step-counter);
    min-width: 28px;
    height: 28px;
    background: #667eea;
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 600;
    margin-right: 12px;
    flex-shrink: 0;
}
.step-item.step-failed {
    background: rgba(229, 62, 62, 0.2);
    border-left-color: #e53e3e;
}
.step-item.step-failed::before {
    background: #e53e3e;
}
.step-content {
    flex: 1;
    min-width: 0;
}
.step-action {
    font-weight: 600;
    color: #e2e8f0;
    display: inline-block;
    padding: 4px 10px;
    background: #4a5568;
    border-radius: 4px;
    font-size: 13px;
    margin-right: 8px;
    margin-bottom: 4px;
}
.step-target {
    color: #a0aec0;
    font-size: 13px;
    word-break: break-word;
    line-height: 1.5;
}
.step-target a {
    color: #63b3ed;
    text-decoration: none;
}
.step-target a:hover {
    text-decoration: underline;
}
.step-value {
    color: #68d391;
    font-weight: 500;
}
.step-element {
    color: #a0aec0;
    font-style: italic;
    font-size: 12px;
}
.step-code-container {
    position: relative;
    margin-top: 8px;
}
.step-code {
    display: block;
    padding: 10px;
    padding-right: 70px;
    background: #1a202c;
    color: #68d391;
    border-radius: 6px;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 11px;
    line-height: 1.4;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 150px;
    overflow-y: auto;
}
.copy-btn {
    position: absolute;
    top: 6px;
    right: 6px;
    padding: 4px 10px;
    background: #4a5568;
    color: #e2e8f0;
    border: none;
    border-radius: 4px;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 4px;
}
.copy-btn:hover {
    background: #667eea;
}
.copy-btn.copied {
    background: #38a169;
}
.step-failed-badge {
    display: inline-block;
    background: #e53e3e;
    color: white;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 600;
    margin-left: 6px;
}
.no-steps {
    color: #a0aec0;
    font-style: italic;
    text-align: center;
    padding: 40px 20px;
}

/* Error section - Top level banner */
.error-banner {
    background: linear-gradient(135deg, rgba(229, 62, 62, 0.2) 0%, rgba(197, 48, 48, 0.2) 100%);
    border-bottom: 2px solid #e53e3e;
    padding: 12px 24px;
    display: flex;
    align-items: center;
    gap: 16px;
    flex-shrink: 0;
}
.error-banner .error-icon {
    font-size: 20px;
}
.error-banner .error-content {
    flex: 1;
}
.error-banner h3 {
    color: #fc8181;
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 4px;
}
.error-banner p {
    color: #feb2b2;
    font-size: 13px;
    line-height: 1.4;
}

/* Bottom panel - Logs */
.logs-panel {
    background: #2d3748;
    border-top: 1px solid #4a5568;
    padding: 12px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
    flex-wrap: wrap;
    gap: 12px;
}
.logs-section {
    display: flex;
    align-items: center;
    gap: 12px;
}
.logs-title {
    font-size: 13px;
    color: #a0aec0;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
}
.logs-links {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
}
.log-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    border-radius: 6px;
    text-decoration: none;
    font-size: 12px;
    font-weight: 500;
    transition: all 0.2s;
}
.log-link:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.log-link.network { background: #667eea; color: white; }
.log-link.console { background: #48bb78; color: white; }
.log-link.selenium { background: #ed8936; color: white; }
.log-link.bs-link { background: #f56565; color: white; }
.log-link.success-link { background: #38a169; color: white; }
.log-link.eux-bo { background: #9f7aea; color: white; }
.log-link.like {
    background: linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%);
    color: white;
    font-weight: 700;
    animation: pulse-like 2s infinite;
    box-shadow: 0 2px 10px rgba(236, 72, 153, 0.4);
}
.log-link.like:hover {
    background: linear-gradient(135deg, #f472b6 0%, #a78bfa 100%);
    transform: translateY(-2px) scale(1.05);
    box-shadow: 0 6px 20px rgba(236, 72, 153, 0.5);
}
@keyframes pulse-like {
    0%, 100% { box-shadow: 0 2px 10px rgba(236, 72, 153, 0.4); }
    50% { box-shadow: 0 4px 20px rgba(236, 72, 153, 0.7); }
}

/* Network Logs Modal */
.modal-overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.8);
    z-index: 1000;
    justify-content: center;
    align-items: center;
}
.modal-overlay.active {
    display: flex;
}
.modal-content {
    background: #2d3748;
    border-radius: 12px;
    width: 90%;
    max-width: 1200px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5);
    border: 1px solid #4a5568;
}
.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid #4a5568;
    background: #1a202c;
    border-radius: 12px 12px 0 0;
}
.modal-title {
    font-size: 16px;
    font-weight: 600;
    color: #e2e8f0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.modal-close {
    background: #e53e3e;
    border: none;
    color: white;
    width: 32px;
    height: 32px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}
.modal-close:hover {
    background: #c53030;
    transform: scale(1.1);
}
.modal-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
}
.network-request {
    background: #1a202c;
    border-radius: 8px;
    margin-bottom: 12px;
    border: 1px solid #4a5568;
    overflow: hidden;
}
.network-request-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: #2d3748;
    cursor: pointer;
    transition: background 0.2s;
}
.network-request-header:hover {
    background: #3d4a5c;
}
.network-method {
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    min-width: 50px;
    text-align: center;
}
.network-method.GET { background: #48bb78; color: white; }
.network-method.POST { background: #667eea; color: white; }
.network-method.PUT { background: #ed8936; color: white; }
.network-method.DELETE { background: #e53e3e; color: white; }
.network-method.OPTIONS { background: #9f7aea; color: white; }
.network-method.PATCH { background: #38b2ac; color: white; }
.network-status {
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}
.network-status.success { background: #38a169; color: white; }
.network-status.redirect { background: #d69e2e; color: white; }
.network-status.client-error { background: #e53e3e; color: white; }
.network-status.server-error { background: #c53030; color: white; }
.network-status.pending { background: #718096; color: white; }
.network-url {
    flex: 1;
    font-size: 12px;
    color: #63b3ed;
    word-break: break-all;
    line-height: 1.4;
}
.network-time {
    font-size: 11px;
    color: #a0aec0;
    white-space: nowrap;
}
.network-expand-icon {
    color: #a0aec0;
    transition: transform 0.2s;
}
.network-request.expanded .network-expand-icon {
    transform: rotate(180deg);
}
.network-request-details {
    display: none;
    padding: 16px;
    border-top: 1px solid #4a5568;
}
.network-request.expanded .network-request-details {
    display: block;
}
.network-section {
    margin-bottom: 16px;
}
.network-section:last-child {
    margin-bottom: 0;
}
.network-section-title {
    font-size: 12px;
    font-weight: 600;
    color: #a0aec0;
    margin-bottom: 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid #4a5568;
}
.network-headers {
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 11px;
    line-height: 1.6;
}
.network-header-item {
    display: flex;
    margin-bottom: 4px;
}
.network-header-name {
    color: #68d391;
    min-width: 200px;
    flex-shrink: 0;
}
.network-header-value {
    color: #e2e8f0;
    word-break: break-all;
}
.network-body-content {
    background: #1a202c;
    padding: 12px;
    border-radius: 6px;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 11px;
    color: #e2e8f0;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 300px;
    overflow-y: auto;
    line-height: 1.5;
}
.no-network-logs {
    text-align: center;
    color: #a0aec0;
    padding: 40px 20px;
    font-style: italic;
}
.network-count-badge {
    background: #667eea;
    color: white;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 12px;
    margin-left: 8px;
}

/* Last successful run info */
.success-run-info {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 16px;
    background: rgba(56, 161, 105, 0.15);
    border: 1px solid #38a169;
    border-radius: 8px;
    font-size: 12px;
}
.success-run-info .label {
    color: #68d391;
    font-weight: 600;
}
.success-run-info .details {
    color: #a0aec0;
}
.success-run-info .date {
    color: #718096;
    font-size: 11px;
}

/* Scrollbar styling - Enhanced visibility */
.steps-container {
    scrollbar-width: auto;
    scrollbar-color: #667eea #1a202c;
}
.steps-container::-webkit-scrollbar {
    width: 14px;
}
.steps-container::-webkit-scrollbar-track {
    background: #1a202c;
    border-left: 1px solid #4a5568;
}
.steps-container::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
    border-radius: 7px;
    border: 2px solid #1a202c;
    min-height: 50px;
}
.steps-container::-webkit-scrollbar-thumb:hover {
    background: linear-gradient(180deg, #7c8ff8 0%, #8b5cb8 100%);
}

/* Scroll indicator hint */
.steps-panel::after {
    content: '↓ Scroll for more steps';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 14px;
    padding: 8px 16px;
    background: linear-gradient(transparent, #2d3748 50%);
    color: #a0aec0;
    font-size: 12px;
    text-align: center;
    pointer-events: none;
    opacity: 0.9;
    transition: opacity 0.3s ease;
}
.steps-panel.scrolled-bottom::after {
    opacity: 0;
}

/* Responsive */
@media (max-width: 1024px) {
    .main-content {
        flex-direction: column;
    }
    .video-panel, .steps-panel {
        width: 100%;
        height: 50%;
    }
    .video-panel {
        border-right: none;
        border-bottom: 1px solid #4a5568;
    }
}
</style>
</head>
<body>
<div class="app-container">
    <!-- Header -->
    <div class="header">
        <div class="header-left">
            <span class="app-name">🎬 BS TestReplay</span>
        </div>
        <div class="header-center">
            <span class="test-name-label">Test name:</span>
            <span class="test-name" title="{{ test_name }}">{{ test_name }}</span>
            {% if build_name %}
            <span class="test-name-label" style="margin-left: 16px;">Player lib version:</span>
            <span class="test-name" title="{{ build_name }}">{{ build_name }}</span>
            {% endif %}
        </div>
        <div class="header-right">
            <span>{{ browser }} {{ browser_version }} | {{ os }} {{ os_version }}</span>
            <span>⏱️ {{ duration }}s</span>
            <span class="status-badge status-{{ status }}">{{ status }}</span>
        </div>
    </div>

    <!-- Error Banner - Only visible when test status is failed -->
    {% if status == 'failed' and error_reason and error_reason != 'Unknown' %}
    <div class="error-banner">
        <span class="error-icon">❌</span>
        <div class="error-content">
            <h3>Failure Details</h3>
            <p>{{ error_reason }}</p>
        </div>
    </div>
    {% endif %}

    <!-- Main content -->
    <div class="main-content">
        <!-- Left panel - Video -->
        <div class="video-panel">
            <div class="video-header">
                🎬 Execution Video
            </div>
            <div class="video-container">
                {% if video_url %}
                <video id="testVideo" controls>
                    <source src="{{ video_url }}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
                <div class="speed-controls">
                    <span>Speed:</span>
                    <button class="speed-btn active" onclick="setSpeed(1)">1x</button>
                    <button class="speed-btn" onclick="setSpeed(2)">2x</button>
                    <button class="speed-btn" onclick="setSpeed(4)">4x</button>
                </div>
                {% else %}
                <div class="video-fallback">
                    <p>Video not embedded in this file.</p>
                    <a href="{{ video_url }}" target="_blank">▶ Open Video in BrowserStack</a>
                </div>
                {% endif %}
            </div>
        </div>

        <!-- Right panel - Steps -->
        <div class="steps-panel" id="stepsPanel">
            <div class="steps-header">
                <span>📝 Steps to Reproduce</span>
                {% if steps %}<span class="steps-count">{{ steps|length }} steps</span>{% endif %}
            </div>
            <div class="steps-container" id="stepsContainer">
                {% if steps %}
                <ul class="steps-list">
                {% for s in steps %}
                    <li class="step-item {% if s.failed %}step-failed{% endif %}">
                        <div class="step-content">
                            <span class="step-action">{{ s.action }}</span>
                            <span class="step-target">
                                {% if s.url %}<a href="{{ s.url }}" target="_blank">{{ s.url }}</a>{% endif %}
                                {% if s.value and not s.is_code %}<span class="step-value">"{{ s.value }}"</span>{% endif %}
                                {% if s.element %}<span class="step-element">{{ s.element }}</span>{% endif %}
                            </span>
                {% if s.is_code and s.value %}
                            <div class="step-code-container">
                                <button class="copy-btn" onclick="copyCode(this)">📋 Copy</button>
                                <code class="step-code">{{ s.value }}</code>
                            </div>
                            {% endif %}
                            {% if s.failed %}<span class="step-failed-badge">FAILED</span>{% endif %}
                        </div>
                    </li>
                {% endfor %}
                </ul>
                {% else %}
                <p class="no-steps">No steps could be extracted from the session logs.</p>
                {% endif %}
            </div>
        </div>
    </div>

    <!-- Bottom panel - Logs & Links -->
    <div class="logs-panel">
        <div class="logs-section">
            <div class="logs-title">
                📋 Logs & Links
            </div>
            <div class="logs-links">
                {% if bs_session_url %}
                <a href="{{ bs_session_url }}" target="_blank" class="log-link bs-link">
                    🔗 Open in BrowserStack
                </a>
                {% endif %}
                {% if eux_bo_url %}
                <a href="{{ eux_bo_url }}" target="_blank" class="log-link eux-bo">
                    🎯 Open EUX BO
                </a>
                {% endif %}
                {% if walkme_network_logs %}
                <button onclick="openNetworkLogsModal()" class="log-link network" style="border: none; cursor: pointer;">
                    🌐 Network <span class="network-count-badge">{{ walkme_network_logs|length }}</span>
                </button>
                {% endif %}
                {% if console_logs_url %}
                <a href="{{ console_logs_url }}" target="_blank" class="log-link console">
                    💻 Console
                </a>
                {% endif %}
                <a href="https://walkme.workproud.com/post/view/16bd0e0c-1aca-4519-a930-ce7e95ee7012/" target="_blank" class="log-link like">
                    🤍 Send me WorkProud
                </a>
            </div>
        </div>

        {% if last_success %}
        <div class="success-run-info">
            <span class="label">✅ Last Successful Run:</span>
            <span class="details">{{ last_success.build_name }}</span>
            <span class="date">{{ last_success.date[:10] if last_success.date else 'N/A' }}</span>
            <a href="{{ last_success.public_url }}" target="_blank" class="log-link success-link">
                View Passed Test
            </a>
        </div>
        {% endif %}
    </div>
</div>

<!-- Network Logs Modal -->
<div id="networkLogsModal" class="modal-overlay">
    <div class="modal-content">
        <div class="modal-header">
            <span class="modal-title">🌐 WalkMe Network Requests
                <span class="network-count-badge">{{ walkme_network_logs|length if walkme_network_logs else 0 }}</span>
            </span>
            <button class="modal-close" onclick="closeNetworkLogsModal()">&times;</button>
        </div>
        <div class="modal-body">
            {% if walkme_network_logs %}
            {% for req in walkme_network_logs %}
            <div class="network-request" id="network-request-{{ loop.index }}">
                <div class="network-request-header" onclick="toggleNetworkRequest({{ loop.index }})">
                    <span class="network-method {{ req.method }}">{{ req.method }}</span>
                    <span class="network-status
                        {%- if req.status >= 200 and req.status < 300 %} success
                        {%- elif req.status >= 300 and req.status < 400 %} redirect
                        {%- elif req.status >= 400 and req.status < 500 %} client-error
                        {%- elif req.status >= 500 %} server-error
                        {%- else %} pending{% endif %}">{{ req.status }} {{ req.statusText }}</span>
                    <span class="network-url">{{ req.url }}</span>
                    <span class="network-time">{% if req.time %}{{ "%.0f"|format(req.time) }}ms{% endif %}</span>
                    <span class="network-expand-icon">▼</span>
                </div>
                <div class="network-request-details">
                    {% if req.startedDateTime %}
                    <div class="network-section">
                        <div class="network-section-title">⏰ Timestamp</div>
                        <div class="network-body-content">{{ req.startedDateTime }}</div>
                    </div>
                    {% endif %}
                    {% if req.request_headers %}
                    <div class="network-section">
                        <div class="network-section-title">📤 Request Headers</div>
                        <div class="network-headers">
                            {% for header in req.request_headers %}
                            <div class="network-header-item">
                                <span class="network-header-name">{{ header.name }}:</span>
                                <span class="network-header-value">{{ header.value }}</span>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                    {% endif %}
                    {% if req.request_body %}
                    <div class="network-section">
                        <div class="network-section-title">📤 Request Body</div>
                        <div class="network-body-content">{{ req.request_body }}</div>
                    </div>
                    {% endif %}
                    {% if req.response_headers %}
                    <div class="network-section">
                        <div class="network-section-title">📥 Response Headers</div>
                        <div class="network-headers">
                            {% for header in req.response_headers %}
                            <div class="network-header-item">
                                <span class="network-header-name">{{ header.name }}:</span>
                                <span class="network-header-value">{{ header.value }}</span>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                    {% endif %}
                    {% if req.response_body %}
                    <div class="network-section">
                        <div class="network-section-title">📥 Response Body</div>
                        <div class="network-body-content">{{ req.response_body }}</div>
                    </div>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
            {% else %}
            <div class="no-network-logs">
                <p>No WalkMe-related network requests found in this session.</p>
            </div>
            {% endif %}
        </div>
    </div>
</div>

<script>
function setSpeed(speed) {
    var video = document.getElementById('testVideo');
    if (video) {
        video.playbackRate = speed;
        // Update button states
        var buttons = document.querySelectorAll('.speed-btn');
        buttons.forEach(function(btn) {
            btn.classList.remove('active');
            if (btn.textContent === speed + 'x') {
                btn.classList.add('active');
            }
        });
    }
}

function copyCode(button) {
    var codeBlock = button.nextElementSibling;
    var code = codeBlock.textContent;

    navigator.clipboard.writeText(code).then(function() {
        // Success - update button
        button.innerHTML = '✅ Copied!';
        button.classList.add('copied');

        // Reset after 2 seconds
        setTimeout(function() {
            button.innerHTML = '📋 Copy';
            button.classList.remove('copied');
        }, 2000);
    }).catch(function(err) {
        // Fallback for older browsers
        var textarea = document.createElement('textarea');
        textarea.value = code;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        
        button.innerHTML = '✅ Copied!';
        button.classList.add('copied');
        setTimeout(function() {
            button.innerHTML = '📋 Copy';
            button.classList.remove('copied');
        }, 2000);
    });
}

// Network Logs Modal Functions
function openNetworkLogsModal() {
    document.getElementById('networkLogsModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeNetworkLogsModal() {
    document.getElementById('networkLogsModal').classList.remove('active');
    document.body.style.overflow = '';
}

function toggleNetworkRequest(index) {
    var request = document.getElementById('network-request-' + index);
    if (request) {
        request.classList.toggle('expanded');
    }
}

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeNetworkLogsModal();
    }
});

// Close modal when clicking outside
document.getElementById('networkLogsModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeNetworkLogsModal();
    }
});

// Handle scroll indicator visibility
document.addEventListener('DOMContentLoaded', function() {
    var stepsContainer = document.getElementById('stepsContainer');
    var stepsPanel = document.getElementById('stepsPanel');

    if (stepsContainer && stepsPanel) {
        function checkScroll() {
            var isAtBottom = stepsContainer.scrollHeight - stepsContainer.scrollTop <= stepsContainer.clientHeight + 10;
            if (isAtBottom) {
                stepsPanel.classList.add('scrolled-bottom');
            } else {
                stepsPanel.classList.remove('scrolled-bottom');
            }
        }

        stepsContainer.addEventListener('scroll', checkScroll);
        // Initial check
        checkScroll();
    }
});
</script>
</body>
</html>
"""


def extract_session_info(url):
    """Extract session ID, build ID, and auth_token from BrowserStack URL"""
    session_match = re.search(r"sessions/([a-zA-Z0-9]+)", url)
    session_id = session_match.group(1) if session_match else None

    # Extract build ID if present in URL
    build_match = re.search(r"builds/([a-zA-Z0-9]+)", url)
    build_id = build_match.group(1) if build_match else None

    # Extract auth_token if present in URL
    auth_match = re.search(r"auth_token=([a-zA-Z0-9]+)", url)
    auth_token = auth_match.group(1) if auth_match else None

    return session_id, build_id, auth_token


def fetch_build_name(build_id):
    """Fetch build name from BrowserStack API using build ID"""
    if not build_id:
        return ""

    auth = (BS_USERNAME, BS_ACCESS_KEY) if BS_USERNAME and BS_ACCESS_KEY else None

    # Try to get build info from builds.json which lists all builds
    if auth:
        try:
            # Use builds.json API to find the build by hashed_id
            r = requests.get(
                "https://api.browserstack.com/automate/builds.json?limit=50",
                auth=auth,
                timeout=30
            )
            if r.status_code == 200:
                builds = r.json()
                for build_data in builds:
                    build = build_data.get("automation_build", {})
                    if build.get("hashed_id", "") == build_id:
                        build_name = build.get("name", "")
                        if build_name:
                            return build_name
        except Exception as e:
            print(f"Failed to fetch build name: {e}")

    return ""


def fetch_session(session_id, auth_token=None):
    """Fetch session details from BrowserStack API"""
    # Try with credentials first
    if BS_USERNAME and BS_ACCESS_KEY:
        try:
            r = requests.get(
                f"https://api.browserstack.com/automate/sessions/{session_id}.json",
                auth=(BS_USERNAME, BS_ACCESS_KEY),
                timeout=30
            )
            if r.status_code == 200:
                data = r.json()
                if "automation_session" in data:
                    return data["automation_session"]
        except Exception as e:
            print(f"API auth failed: {e}")

    # Try with auth_token if available
    if auth_token:
        try:
            # BrowserStack public URLs use auth_token parameter
            r = requests.get(
                f"https://api.browserstack.com/automate/sessions/{session_id}.json?auth_token={auth_token}",
                timeout=30
            )
            if r.status_code == 200:
                data = r.json()
                if "automation_session" in data:
                    return data["automation_session"]
        except Exception as e:
            print(f"Auth token request failed: {e}")

    # If both methods failed, raise error with helpful message
    raise Exception(
        "Unable to fetch session. Please check:\n"
        "1. Environment variables AUTOMATION_BS_USER and AUTOMATION_BS_PASS are set correctly\n"
        "2. The session URL is valid and includes auth_token parameter\n"
        "3. The session has not expired"
    )


MAX_LOG_SIZE = 500_000  # 500KB limit per log source


def fetch_logs(session_id, auth_token=None):
    """Fetch text logs from BrowserStack which contain Selenium commands"""
    auth = (BS_USERNAME, BS_ACCESS_KEY) if BS_USERNAME and BS_ACCESS_KEY else None

    # Build query string for auth_token fallback
    token_param = f"?auth_token={auth_token}" if auth_token else ""

    # Only fetch the primary logs endpoint (not all 4) to save memory
    log_endpoints = [
        f"https://api.browserstack.com/automate/sessions/{session_id}/logs",
        f"https://api.browserstack.com/automate/sessions/{session_id}/seleniumlogs",
    ]

    combined_logs = ""
    for endpoint in log_endpoints:
        if len(combined_logs) >= MAX_LOG_SIZE:
            break
        try:
            if auth:
                r = requests.get(endpoint, auth=auth, timeout=30)
                if r.status_code == 200 and r.text:
                    combined_logs += r.text[:MAX_LOG_SIZE] + "\n"
                    continue
            if auth_token:
                r = requests.get(endpoint + token_param, timeout=30)
                if r.status_code == 200 and r.text:
                    combined_logs += r.text[:MAX_LOG_SIZE] + "\n"
        except Exception:
            continue

    return combined_logs[:MAX_LOG_SIZE]


def fetch_walkme_network_logs(session_id, auth_token=None):
    """Fetch network logs from BrowserStack and filter only walkme.com related requests"""
    import json as json_module
    auth = (BS_USERNAME, BS_ACCESS_KEY) if BS_USERNAME and BS_ACCESS_KEY else None
    token_param = f"?auth_token={auth_token}" if auth_token else ""

    network_logs_endpoint = f"https://api.browserstack.com/automate/sessions/{session_id}/networklogs"

    walkme_requests = []

    try:
        response = None
        if auth:
            response = requests.get(network_logs_endpoint, auth=auth, timeout=30)
        if (not response or response.status_code != 200) and auth_token:
            response = requests.get(network_logs_endpoint + token_param, timeout=30)

        if response and response.status_code == 200:
            # Limit raw response size before parsing
            raw = response.text[:2_000_000]  # max 2MB
            try:
                har_data = json_module.loads(raw)
                entries = []
                if isinstance(har_data, dict):
                    if 'log' in har_data and 'entries' in har_data['log']:
                        entries = har_data['log']['entries']
                    elif 'entries' in har_data:
                        entries = har_data['entries']
                elif isinstance(har_data, list):
                    entries = har_data

                for entry in entries[:300]:  # max 300 entries
                    request_data = entry.get('request', {})
                    response_data = entry.get('response', {})
                    url = request_data.get('url', '')

                    if 'walkme.com' in url.lower() or 'walkme' in url.lower():
                        filtered_entry = {
                            'url': url,
                            'method': request_data.get('method', 'GET'),
                            'status': response_data.get('status', 0),
                            'statusText': response_data.get('statusText', ''),
                            'time': entry.get('time', 0),
                            'startedDateTime': entry.get('startedDateTime', ''),
                            'request_headers': [],
                            'response_headers': [],
                            'request_body': '',
                            'response_body': ''
                        }
                        post_data = request_data.get('postData', {})
                        if post_data:
                            filtered_entry['request_body'] = post_data.get('text', '')[:500]
                        content = response_data.get('content', {})
                        if content:
                            response_text = content.get('text', '')
                            filtered_entry['response_body'] = response_text[:1000] + ('... [truncated]' if len(response_text) > 1000 else '')
                        walkme_requests.append(filtered_entry)
                        if len(walkme_requests) >= 50:  # max 50 walkme entries
                            break
            except json_module.JSONDecodeError:
                for line in raw.split('\n')[:200]:
                    if 'walkme' in line.lower():
                        walkme_requests.append({
                            'url': line.strip()[:500], 'method': 'N/A', 'status': 'N/A',
                            'statusText': '', 'time': 0, 'startedDateTime': '',
                            'request_headers': [], 'response_headers': [],
                            'request_body': '', 'response_body': ''
                        })
        else:
            print(f"Failed to fetch network logs: {response.status_code if response else 'No response'}")

    except Exception as e:
        print(f"Error fetching network logs: {e}")

    print(f"Found {len(walkme_requests)} WalkMe-related network requests")
    return walkme_requests


def fetch_video(video_url):
    """Download video and return base64 encoded string for embedding"""
    auth = (BS_USERNAME, BS_ACCESS_KEY) if BS_USERNAME and BS_ACCESS_KEY else None

    try:
        # Try direct URL first (may be publicly accessible with token in URL)
        r = requests.get(video_url, timeout=120)
        if r.status_code != 200 and auth:
            r = requests.get(video_url, auth=auth, timeout=120)
        r.raise_for_status()
        return base64.b64encode(r.content).decode('utf-8')
    except Exception as e:
        print(f"Failed to download video: {e}")
        return None


def get_eux_bo_domain(test_name):
    """Determine EUX BO domain based on test name or project name.

    Returns:
        - eux.int.eu01.walkmex.com if test_name contains _eu_ or _EU_
        - eux.int.us01.walkmex.com if test_name contains _us_ or _US_
        - eux-prod.walkmernd.com (default)
    """
    if not test_name:
        return "eux-prod.walkmernd.com"

    # Check for EU pattern (case insensitive)
    if "_eu_" in test_name.lower():
        return "eux.int.eu01.walkmex.com"

    # Check for US pattern (case insensitive)
    if "_us_" in test_name.lower():
        return "eux.int.us01.walkmex.com"

    # Default domain
    return "eux-prod.walkmernd.com"


def extract_eux_bo_url(logs, test_name=None):
    """Extract GUID from WalkMe snippet URL in logs and return EUX BO URL

    Searches for URLs like:
    https://cdn.walkme.com/users/GUID/test/walkme_GUID_https.js
    https://cdn-eu01.walkme.cloud.sap/users/GUID/test/walkme_GUID_https.js
    https://cdn-us01.walkme.cloud.sap/users/GUID/test/walkme_GUID_https.js
    Extracts GUID: e4c02787c1a845c886757633064bf50d
    Maps to email and returns EUX BO URL

    Args:
        logs: Log content to search for GUID
        test_name: Test name used to determine the correct EUX BO domain
    """
    if not logs:
        return None

    # Determine the correct domain based on test name
    domain = get_eux_bo_domain(test_name)
    print(f"Using EUX BO domain: {domain}")

    # Pattern to match WalkMe CDN URLs with GUID
    # Matches: cdn.walkme.com, cdn-eu01.walkme.cloud.sap, cdn-us01.walkme.cloud.sap
    # Example: cdn.walkme.com/users/GUID/test/walkme_GUID_https.js
    # Example: cdn-eu01.walkme.cloud.sap/users/GUID/test/walkme_GUID_https.js
    guid_pattern = r'cdn(?:-[a-z]{2}\d{2})?\.walkme(?:\.cloud\.sap|\.com)/users/([a-f0-9]{32})/'

    match = re.search(guid_pattern, logs, re.IGNORECASE)
    if match:
        guid = match.group(1).lower()
        print(f"Found WalkMe GUID: {guid}")

        # Look up email from mapping
        email = GUID_TO_EMAIL_MAPPING.get(guid)
        if email:
            eux_bo_url = f"https://{domain}/accountConfiguration/userPlayerInfo/{email}"
            print(f"EUX BO URL: {eux_bo_url}")
            return eux_bo_url
        else:
            print(f"GUID {guid} not found in mapping")
    else:
        # Try alternative pattern - look for walkme_GUID in the JS filename
        # This matches: walkme_93c2b84bf8d141e58566769658133ffd_https.js
        alt_pattern = r'walkme_([a-f0-9]{32})_https\.js'
        match = re.search(alt_pattern, logs, re.IGNORECASE)
        if match:
            guid = match.group(1).lower()
            print(f"Found WalkMe GUID (alt pattern): {guid}")
            email = GUID_TO_EMAIL_MAPPING.get(guid)
            if email:
                eux_bo_url = f"https://{domain}/accountConfiguration/userPlayerInfo/{email}"
                print(f"EUX BO URL: {eux_bo_url}")
                return eux_bo_url
            else:
                print(f"GUID {guid} not found in mapping")

    print("No WalkMe GUID found in logs")
    return None


def get_test_name_without_random(test_name):
    """Remove random number suffix from test name to find similar tests.
    Returns the base name WITH parameters (project name) for exact matching.
    The bracket content is the PROJECT NAME and must match exactly.
    Examples:
        'test_login_12345' -> 'test_login'
        'test_18_swt_auto_2[SAP_concur]_5537' -> 'test_18_swt_auto_2[SAP_concur]'
        'test_05_onboarding[SAP_US_concur]_6593' -> 'test_05_onboarding[SAP_US_concur]'
    """
    if not test_name:
        return test_name

    # Remove trailing random number suffix (e.g., _6593, _12345)
    # This handles both 'test_name_1234' and 'test_name[param]_1234'
    cleaned = re.sub(r'_\d+$', '', test_name)

    return cleaned.strip()


def find_last_successful_run(test_name, current_session_id, current_build_id=None):
    """Find the last successful run of the same test.

    First searches in the SAME build (since tests often run together),
    then searches in other recent builds.

    IMPORTANT: The bracket content [project_name] must match exactly.

    Returns dict with: build_id, session_id, date, public_url, or None if not found
    """
    if not BS_USERNAME or not BS_ACCESS_KEY:
        print("Cannot search for last successful run: BrowserStack credentials not set")
        return None

    auth = (BS_USERNAME, BS_ACCESS_KEY)
    base_test_name = get_test_name_without_random(test_name)

    if not base_test_name:
        return None

    # Extract project name from brackets for targeted debug
    project_match = re.search(r'\[([^]]+)]', base_test_name)
    project_name = project_match.group(1) if project_match else None

    print(f"Searching for last successful run of test: '{test_name}'")
    print(f"  Looking for exact match: '{base_test_name}'")
    if project_name:
        print(f"  Project filter: '{project_name}'")

    # Helper function to search sessions in a build
    def search_build_sessions(search_build_id, search_build_name):
        sessions_url = (
            f"https://api.browserstack.com/automate/builds/"
            f"{search_build_id}/sessions.json?limit=50"
        )
        try:
            sr = requests.get(sessions_url, auth=auth, timeout=60)
            if sr.status_code != 200:
                return None, 0, 0

            sessions = sr.json()
            matching_project_count = 0
            passed_count = 0

            for session_data in sessions:
                session = session_data.get("automation_session", {})
                session_name = session.get("name", "")
                session_status = session.get("status", "")
                session_id = session.get("hashed_id", "")

                # Skip current session
                if session_id == current_session_id:
                    continue

                # Only consider passed sessions
                if session_status != "passed":
                    continue

                passed_count += 1

                # Get base name for comparison
                session_base_name = get_test_name_without_random(session_name)

                # Count tests with matching project name
                if project_name and project_name.lower() in session_name.lower():
                    matching_project_count += 1

                # Exact match required: same test name AND same project
                if session_base_name == base_test_name:
                    created_at = session.get("created_at", "")
                    public_url = session.get("public_url", "")
                    if not public_url:
                        public_url = (
                            f"https://automate.browserstack.com/builds/"
                            f"{search_build_id}/sessions/{session_id}"
                        )

                    return {
                        "build_id": search_build_id,
                        "build_name": search_build_name,
                        "session_id": session_id,
                        "session_name": session_name,
                        "date": created_at,
                        "public_url": public_url
                    }, passed_count, matching_project_count

            return None, passed_count, matching_project_count

        except requests.RequestException as req_err:
            print(f"Error fetching sessions for build {search_build_id}: {req_err}")
            return None, 0, 0

    try:
        total_passed_sessions = 0
        total_matching_project = 0

        # FIRST: Search in the SAME build if build_id is provided
        if current_build_id:
            print(f"  First checking current build: {current_build_id}")
            result, passed, matching = search_build_sessions(current_build_id, "Current Build")
            total_passed_sessions += passed
            total_matching_project += matching
            if result:
                print(f"  MATCH FOUND in same build: {result['session_name']}")
                print(f"    Session: {result['session_id']}")
                return result
            else:
                print(f"    No match in current build ({passed} passed, "
                      f"{matching} with {project_name} project)")

        # SECOND: Search in other recent builds
        builds_url = "https://api.browserstack.com/automate/builds.json?limit=10"
        r = requests.get(builds_url, auth=auth, timeout=60)
        if r.status_code != 200:
            print(f"Failed to fetch builds: {r.status_code}")
            return None

        builds = r.json()
        print(f"  Checking {len(builds)} recent builds...")

        builds_with_project = []

        for build_idx, build_data in enumerate(builds):
            build = build_data.get("automation_build", {})
            build_hashed_id = build.get("hashed_id", "")
            build_name = build.get("name", "Unknown Build")

            # Skip if this is the same build we already searched
            if build_hashed_id == current_build_id:
                continue

            result, passed, matching = search_build_sessions(build_hashed_id, build_name)
            total_passed_sessions += passed
            total_matching_project += matching

            if result:
                print(f"  MATCH FOUND: {result['session_name']}")
                print(f"    Build: {build_name} ({build_hashed_id})")
                print(f"    Session: {result['session_id']}")
                return result

            # Track builds that have matching project tests
            if matching > 0:
                builds_with_project.append(f"{build_name} ({matching} tests)")

        print(f"  Summary: {total_passed_sessions} passed sessions, "
              f"{total_matching_project} with {project_name} project")

        # Print builds that had matching project tests
        if builds_with_project:
            print(f"  Builds with {project_name} project:")
            for b in builds_with_project[:10]:
                print(f"    - {b}")

        print("No previous successful run found with same test name and project")
        return None

    except Exception as e:
        print(f"Error searching for last successful run: {e}")
        return None


def parse_steps(logs):
    """Parse BrowserStack text logs to extract clean, human-readable steps for QA"""
    steps = []
    lines = logs.split("\n")
    last_element_selector = None
    last_url = None

    # Pre-scan logs to detect if mailinator or temp mail URLs exist
    logs_lower = logs.lower()
    has_mailinator = any(pattern in logs_lower for pattern in [
        "mailinator.com", "mailinator.", "mail.tm", "tempmail", "guerrillamail"
    ])
    if has_mailinator:
        print("DEBUG: Mailinator/temp mail URL detected in logs - will add 'Create user' step")

    # Also find all mailinator URLs in the logs for reference
    mailinator_urls = re.findall(r'https?://[^\s"\'<>)\]]*mailinator[^\s"\'<>)\]]*', logs, re.IGNORECASE)
    if mailinator_urls:
        print(f"DEBUG: Found {len(mailinator_urls)} mailinator URLs in logs")
        for url in mailinator_urls[:3]:  # Show first 3
            print(f"  - {url}")

    # Extract the first timestamp from logs to use as base time
    first_timestamp = None

    # Find all timestamps in the logs to understand the time range
    timestamp_pattern = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?|\d{2}:\d{2}:\d{2}(?:\.\d+)?)'
    all_timestamps = []
    for line in lines:
        ts_match = re.search(timestamp_pattern, line)
        if ts_match:
            all_timestamps.append(ts_match.group(1))

    if all_timestamps:
        first_timestamp = all_timestamps[0]
        print(f"Log time range: {first_timestamp} to {all_timestamps[-1]}")

    def parse_timestamp(ts_str):
        """Parse timestamp string to seconds from start"""
        if not ts_str:
            return 0
        try:
            # Handle different timestamp formats
            if ' ' in ts_str:
                # Full datetime: 2024-01-01 12:34:56.789
                parts = ts_str.split(' ')[1] if ' ' in ts_str else ts_str
            else:
                parts = ts_str

            time_parts = parts.split(':')
            if len(time_parts) >= 3:
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                seconds = float(time_parts[2])
                return hours * 3600 + minutes * 60 + seconds
        except (ValueError, IndexError):
            pass
        return 0

    def get_relative_time(ts_str, base_ts_str):
        """Get time in seconds relative to base timestamp"""
        if not ts_str or not base_ts_str:
            return 0
        current = parse_timestamp(ts_str)
        base = parse_timestamp(base_ts_str)
        return max(0, current - base)

    def clean_selector(selector):
        """Clean up CSS selector to be human readable - do NOT truncate"""
        if not selector:
            return None
        # Unescape escaped characters (\" -> ", \\ -> \, etc.)
        try:
            # First try to decode unicode escapes
            selector = selector.encode('utf-8').decode('unicode_escape')
        except (UnicodeDecodeError, UnicodeEncodeError):
            # If that fails, just do simple replacements
            pass
        # Clean up common escape sequences manually
        selector = selector.replace('\\"', '"').replace("\\'", "'")
        selector = selector.replace('\\n', ' ').replace('\\t', ' ')
        # Remove trailing backslashes that might be leftover
        selector = re.sub(r'\\+$', '', selector)
        # Just clean up leading/trailing special chars but keep the full selector
        selector = selector.strip('[]"\' =')
        # If it's just punctuation or too short, return None
        if len(selector) < 2 or not re.search(r'[a-zA-Z]', selector):
            return None
        return selector

    def format_value(raw_value):
        """Format value from comma-separated chars to single string, preserving spaces"""
        if not raw_value:
            return None
        # Remove surrounding brackets
        value_str = raw_value.strip('[]')
        # Split by comma and process each part
        parts = re.split(r',', value_str)
        # Clean each part - remove quotes but preserve the character (including spaces)
        result_chars = []
        for p in parts:
            p = p.strip()
            # Remove surrounding quotes
            if (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")):
                p = p[1:-1]
            # Preserve the character including space
            if p or p == '':  # Empty string after removing quotes means it was a space
                result_chars.append(p if p else ' ')
        result = ''.join(result_chars)
        # Also handle case where value is already a single string with spaces
        if not result_chars and value_str:
            result = value_str.strip('"\'')
        return result if result else None

    def is_backspace_sequence(value):
        """Check if value is a backspace sequence"""
        if not value:
            return False
        value_lower = value.lower()
        # Check for backspace patterns
        backspace_indicators = ['backspace', '\ue003', 'back_space']
        return any(b in value_lower for b in backspace_indicators)

    for line in lines:
        step = None
        line_lower = line.lower()

        # Extract timestamp from this line
        line_timestamp = None
        ts_match = re.search(timestamp_pattern, line)
        if ts_match:
            line_timestamp = get_relative_time(ts_match.group(1), first_timestamp)

        # Skip browserstack_executor annotate commands - internal info only
        if "browserstack_executor" in line_lower and "annotate" in line_lower:
            continue

        # Skip pure RESPONSE lines - they are echoes of commands, not new actions
        # But don't skip lines that contain actual command data
        if line.strip().startswith("RESPONSE") and "/url" not in line_lower and "/element" not in line_lower:
            continue

        # Skip lines that are just status responses without command data
        if ('"status":' in line_lower and '"url"' not in line_lower
                and '"using"' not in line_lower and '/click' not in line_lower
                and '/value' not in line_lower):
            continue

        # Skip lines that are just session info or status
        if '"sessionId"' in line and '"value"' not in line and '"url"' not in line:
            continue

        # Track the last element found (for context in click/type actions)
        element_match = None
        if "element" in line_lower and "elements" not in line_lower:
            # Pattern 1: {"using":"css selector","value":"..."}
            # Use a robust regex that handles escaped quotes in the value
            using_match = re.search(r'"using"\s*:\s*"([^"]+)"', line)

            # For value, we need to handle escaped quotes like \"
            # Find "value":" and then capture until we hit an unescaped "
            value_start = re.search(r'"value"\s*:\s*"', line)
            if value_start and using_match:
                start_pos = value_start.end()
                # Manually find the end of the string, handling escaped quotes
                selector_value_str = ""
                i = start_pos
                while i < len(line):
                    if line[i] == '"' and (i == start_pos or line[i - 1] != '\\'):
                        break
                    selector_value_str += line[i]
                    i += 1
                if selector_value_str:
                    element_match = (using_match.group(1), selector_value_str)

            # Pattern 2: By.CSS_SELECTOR, "#id"
            if not element_match:
                by_match = re.search(r'By\.(\w+)[,\s]+["\']([^"\']+)["\']', line)
                if by_match:
                    element_match = (by_match.group(1).lower(), by_match.group(2))

            # Pattern 3: find_element_by_xxx("value")
            if not element_match:
                by_method_match = re.search(r'find_element_by_(\w+)\s*\(\s*["\']([^"\']+)["\']', line)
                if by_method_match:
                    element_match = (by_method_match.group(1), by_method_match.group(2))

            if element_match:
                _, selector_value = element_match

                # Keep the FULL selector value - no truncation or extraction
                # This ensures QA tester sees exactly what element was targeted
                last_element_selector = selector_value

                # Clean up the selector but don't truncate
                cleaned = clean_selector(last_element_selector)
                if cleaned:
                    last_element_selector = cleaned
                continue

        # Parse navigation commands
        nav_detected = False
        if "/url" in line_lower or "navigat" in line_lower or "driver.get" in line_lower or ".get(" in line_lower:
            url_match = re.search(r'"url"\s*:\s*"([^"]+)"', line)
            if not url_match:
                url_match = re.search(r'\.get\s*\(\s*["\']([^"\']+)["\']', line, re.IGNORECASE)
            if not url_match:
                # More permissive URL regex to capture full URLs including query strings
                url_match = re.search(r'(https?://[^\s"\'<>]+?)(?=["\'\s<>]|$)', line)

            if url_match:
                url = url_match.group(1)
                # Clean trailing punctuation that might have been captured
                url = url.rstrip('.,;:')
                if ('localhost' in url.lower() or '127.0.0.1' in url
                        or 'file://' in url.lower() or 'data:' in url.lower()):
                    continue
                if url == last_url:
                    continue
                last_url = url
                step = {"action": "Open", "url": url, "element": None, "value": None, "failed": False,
                        "log_time": line_timestamp}
                nav_detected = True

        # Also check for mailinator URLs that might be in different format (e.g., window.location or redirect)
        if not nav_detected and "mailinator" in line_lower:
            mailinator_match = re.search(r'(https?://[^\s"\'<>]*mailinator[^\s"\'<>]*)', line, re.IGNORECASE)
            if mailinator_match:
                url = mailinator_match.group(1).rstrip('.,;:"\']')
                if url != last_url:
                    last_url = url
                    step = {"action": "Open", "url": url, "element": None, "value": None, "failed": False,
                            "log_time": line_timestamp}
                    print(f"DEBUG: Captured mailinator URL from special pattern: {url}")
                nav_detected = True

        # Parse click commands - skip timeout/wait related lines
        if not nav_detected and ("/click" in line_lower or ".click(" in line_lower or "click()" in line_lower):
            # Skip if this is a wait condition or timeout error, not an actual click
            if ("element_to_be_clickable" in line_lower or "expected_conditions" in line_lower
                    or "timeout" in line_lower or "webdriverwait" in line_lower):
                continue

            element_display = clean_selector(last_element_selector)

            # Skip click if we don't have a meaningful element selector
            if not element_display:
                last_element_selector = None
                continue

            # Just show "Click" with element name - avoid guessing button/link type to prevent false positives
            step = {"action": "Click", "url": None, "element": f'"{element_display}"', "value": None, "failed": False,
                    "screenshot": None, "log_time": line_timestamp}
            last_element_selector = None

        # Parse send keys / typing - skip if timeout error (that's a failed wait, not typing)
        elif "/value" in line_lower or "send_keys" in line_lower or "sendkeys" in line_lower:
            # Extract typed value
            value_match = re.search(r'"value"\s*:\s*\[([^]]+)]', line)
            if not value_match:
                value_match = re.search(r'send_keys?\s*\(\s*["\']([^"\']+)["\']', line, re.IGNORECASE)

            raw_val = value_match.group(1) if value_match else None

            # Check for backspace sequence - skip these entirely (too noisy)
            if is_backspace_sequence(raw_val):
                last_element_selector = None
                continue  # Skip Clear steps
            else:
                val = format_value(raw_val)
                element_display = clean_selector(last_element_selector)
                elem_lower = (element_display or "").lower()

                # Be strict about password/username detection to avoid false positives
                # Only match if it's clearly an input field with type="password" or name="password" etc.
                is_password_field = False
                is_username_field = False

                # Check for actual password input patterns (type="password" or name="password" or id="password")
                if element_display:
                    # Only match if password/user appears as the primary identifier, not just anywhere in selector
                    password_patterns = [
                        'type="password"', "type='password'",
                        'name="password"', "name='password'",
                        'id="password"', "id='password'",
                        '[type=password]', 'input#password',
                        'name="pwd"', 'id="pwd"'
                    ]
                    username_patterns = [
                        'type="email"', "type='email'",
                        'name="username"', "name='username'",
                        'name="email"', "name='email'",
                        'id="username"', "id='username'",
                        'id="email"', "id='email'",
                        'input#username', 'input#email',
                        '[type=email]'
                    ]

                    for pattern in password_patterns:
                        if pattern in elem_lower:
                            is_password_field = True
                            break

                    for pattern in username_patterns:
                        if pattern in elem_lower:
                            is_username_field = True
                            break

                # Create step - use generic "Enter text" for most cases to avoid hallucination
                if is_password_field:
                    step = {"action": "Enter password", "url": None,
                            "element": f'in "{element_display}"' if element_display else None, "value": val,
                            "failed": False, "log_time": line_timestamp}
                elif is_username_field:
                    step = {"action": "Enter username/email", "url": None,
                            "element": f'in "{element_display}"' if element_display else None, "value": val,
                            "failed": False, "log_time": line_timestamp}
                elif element_display:
                    step = {"action": "Enter text", "url": None, "element": f'in "{element_display}"', "value": val,
                            "failed": False, "log_time": line_timestamp}
                elif val:
                    # Only show if we have a value, even without element
                    step = {"action": "Enter text", "url": None, "element": None, "value": val, "failed": False,
                            "log_time": line_timestamp}
                # Skip if we have neither element nor value
                last_element_selector = None

        # Skip wait/sleep commands - they create too much noise
        # elif any(w in line_lower for w in ["time.sleep", "sleep(", "webdriverwait", "explicit"]):
        #     step = {"action": "Wait", "url": None, "element": "for page to load", "value": None, "failed": False}

        # Parse execute script / inject snippet commands - show ALL as "Run in console"
        elif "/execute" in line_lower or "execute_script" in line_lower or "executescript" in line_lower:
            # Try to extract the script content
            script_match = re.search(r'"script"\s*:\s*"((?:[^"\\]|\\.)*)"', line)
            if not script_match:
                script_match = re.search(r'execute_script\s*\(\s*["\'](.+?)["\']', line, re.DOTALL)

            if script_match:
                script_content = script_match.group(1)
                # Unescape the script content
                try:
                    script_content = script_content.encode('utf-8').decode('unicode_escape')
                except (UnicodeDecodeError, UnicodeEncodeError):
                    pass
                script_content = script_content.replace('\\n', '\n').replace('\\t', '\t')

                # Skip submitForm scripts - they are internal form submission helpers
                if 'submitForm' in script_content or '/* submitForm */' in script_content:
                    continue

                # Skip very short return statements (internal utility)
                if script_content.strip().startswith('return ') and len(script_content) < 50:
                    continue

                # Truncate long scripts for display
                display_script = script_content
                if len(display_script) > 500:
                    display_script = display_script[:500] + "..."

                # Show all execute script steps as "Run in console"
                step = {"action": "Run in console", "url": None, "element": None, "value": display_script,
                        "failed": False, "is_code": True, "log_time": line_timestamp}

        # Skip select/dropdown - they are confusing without proper context
        # Parse switch to frame/window
        elif "switch_to" in line_lower or "switchto" in line_lower:
            if "frame" in line_lower:
                step = {"action": "Switch to", "url": None, "element": "iframe", "value": None, "failed": False,
                        "log_time": line_timestamp}
            elif "window" in line_lower or "tab" in line_lower:
                step = {"action": "Switch to", "url": None, "element": "new window/tab", "value": None, "failed": False,
                        "log_time": line_timestamp}

        if step:
            # Skip steps with errors - only show successful steps
            # Error details are shown separately in the error message section
            is_error_line = any(
                err in line_lower for err in ['"error"', 'exception', 'nosuchelement', 'timeout', 'stale'])
            if not is_error_line:
                steps.append(step)

    # If no steps found with structured parsing, try simpler text-based parsing
    if not steps:
        for line in lines:
            line_lower = line.lower()
            # Extract timestamp for fallback steps
            ts_match = re.search(timestamp_pattern, line)
            fallback_time = get_relative_time(ts_match.group(1), first_timestamp) if ts_match else None

            if any(kw in line_lower for kw in ['navigate', 'get(', 'goto', 'open', 'loading', 'url']):
                url_match = re.search(r'https?://[^\s"\'<>)\]]+', line)
                if url_match:
                    url = url_match.group(0)
                    if 'localhost' not in url.lower() and '127.0.0.1' not in url and url != last_url:
                        steps.append({"action": "Open", "url": url, "element": None, "value": None, "failed": False,
                                      "log_time": fallback_time})
                        last_url = url
            # Skip generic click and type steps - they are not useful without element context

    # Post-process: remove failed steps in the middle (keep only last failed step)
    # and deduplicate more aggressively
    cleaned_steps = []
    prev_step = None
    seen_actions = set()  # Track unique action+element combinations

    # First pass: check if there's a mailinator URL anywhere in the steps
    has_mailinator_step = False
    for i, step in enumerate(steps):
        if step["action"] == "Open" and step.get("url"):
            url_lower = step["url"].lower()
            mailinator_patterns = [
                "mailinator.com", "mailinator.", "mail.tm", "tempmail", "guerrillamail"
            ]
            if any(pattern in url_lower for pattern in mailinator_patterns):
                has_mailinator_step = True
                break

    # Collect all mailinator URLs from steps (to group them together)
    mailinator_steps = []
    non_mailinator_steps = []

    for step in steps:
        if step["action"] == "Open" and step.get("url"):
            url_lower = step["url"].lower()
            is_mailinator = any(pattern in url_lower for pattern in [
                "mailinator.com", "mailinator.", "/mailinator",
                "mail.tm", "tempmail", "guerrillamail"
            ])
            if is_mailinator:
                mailinator_steps.append(step)
                continue
        non_mailinator_steps.append(step)

    # Track if we've added the "Create user" step and mailinator steps
    create_user_added = False
    mailinator_steps_added = False

    for i, step in enumerate(non_mailinator_steps):
        # Create a signature for this step to detect duplicates
        # Include URL for navigation steps to avoid deduplicating different page visits
        if step["action"] == "Open" and step.get("url"):
            step_signature = f"{step['action']}|{step.get('url', '')}"
        else:
            step_signature = f"{step['action']}|{step.get('element', '')}|{step.get('value', '')}"

        # Skip exact duplicate steps (same action, element, and value)
        if step_signature in seen_actions:
            continue

        # Skip duplicate consecutive steps (looser check)
        if prev_step:
            if step["action"] == prev_step["action"] and step["element"] == prev_step["element"]:
                # Same action and element - skip unless value is significantly different
                prev_val = prev_step.get("value") or ""
                curr_val = step.get("value") or ""
                if prev_val == curr_val or (not prev_val and not curr_val):
                    continue

        # Check for user management page - add "Create user using API" step after it
        # Then add ALL mailinator steps right after
        if step["action"] == "Open" and step.get("url") and has_mailinator_step and not create_user_added:
            url_lower = step["url"].lower()
            # Add "Create user" step after user management page navigation
            if any(pattern in url_lower for pattern in ["/users/manage", "/users", "/user-management", "manage-users"]):
                cleaned_steps.append(step)
                seen_actions.add(step_signature)

                # Now add the "Create user using API" step
                print("DEBUG: User management page detected, adding 'Create user using API' step after it")
                create_user_step = {
                    "action": "Create user using API",
                    "url": None,
                    "element": "(API call to create test user before email verification)",
                    "value": None,
                    "failed": False,
                    "log_time": step.get("log_time")
                }
                cleaned_steps.append(create_user_step)
                create_user_added = True
                print("Added 'Create user using API' step after user management page")

                # Now add ALL mailinator steps right here (grouped together)
                if mailinator_steps and not mailinator_steps_added:
                    seen_mailinator_urls = set()
                    for ms in mailinator_steps:
                        ms_url = ms.get("url", "")
                        # Skip duplicate mailinator URLs
                        if ms_url in seen_mailinator_urls:
                            continue
                        seen_mailinator_urls.add(ms_url)

                        # Create a cleaner step for email verification
                        if "msgid=" in ms_url.lower():
                            action_text = "Click verification link in email"
                        else:
                            action_text = "Check verification email"

                        email_check_step = {
                            "action": action_text,
                            "url": ms_url,
                            "element": "(mailinator inbox)",
                            "value": None,
                            "failed": False,
                            "log_time": ms.get("log_time")
                        }
                        cleaned_steps.append(email_check_step)
                        print(f"Added mailinator step: {action_text}")
                    mailinator_steps_added = True

                prev_step = cleaned_steps[-1] if cleaned_steps else None
                continue

        cleaned_steps.append(step)
        seen_actions.add(step_signature)
        prev_step = step

    # Build final steps list (only successful steps)
    final_steps = [step for step in cleaned_steps if not step.get("failed", False)]

    return final_steps


def get_all_hashed_build_ids(build_name_or_hash):
    """Get ALL hashed build IDs for a given build name.

    Args:
        build_name_or_hash: Build name like "20260412-064121-6903a"
                           OR hashed_id like "910d848cde11c50835c0537c3b8899552067f48c"

    Returns:
        List of hashed build ID strings (all matching builds)

    Raises:
        ValueError if build not found or API error
    """
    # Check if it's already a hashed_id (40 character hex string)
    if len(build_name_or_hash) == 40 and all(c in '0123456789abcdef' for c in build_name_or_hash.lower()):
        print(f"Input appears to be a hashed_id already: {build_name_or_hash}")
        return [build_name_or_hash]

    auth = (BS_USERNAME, BS_ACCESS_KEY)

    # Fetch MORE builds to increase chance of finding all matches
    all_builds = []
    offset = 0
    while True:
        response = requests.get(
            f"https://api-cloud.browserstack.com/automate/builds.json?limit=100&offset={offset}",
            auth=auth,
            timeout=30
        )
        response.raise_for_status()
        builds_page = response.json()
        if not builds_page:
            break
        all_builds.extend(builds_page)
        if len(builds_page) < 100:
            break
        offset += 100

    print(f"Searching through {len(all_builds)} recent builds for '{build_name_or_hash}'...")

    # Search through ALL fetched builds for matching name and collect ALL matches
    hashed_ids = []
    for build_item in all_builds:
        build_info = build_item.get("automation_build", {})
        build_name = build_info.get("name", "")
        hashed_id = build_info.get("hashed_id", "")

        if build_name == build_name_or_hash:
            hashed_ids.append(hashed_id)
            print(f"  Found matching build: {hashed_id} (status: {build_info.get('status', 'unknown')}, duration: {build_info.get('duration', 0)}s)")

    if hashed_ids:
        print(f"\n✓ Found {len(hashed_ids)} hashed build ID(s) for '{build_name_or_hash}'")
        return hashed_ids

    # Build not found - provide helpful error message with available builds
    available_builds = []
    for b in all_builds[:10]:
        build_info = b.get("automation_build", {})
        available_builds.append(f"{build_info.get('name', 'Unknown')} ({build_info.get('hashed_id', 'N/A')[:20]}...)")

    raise ValueError(
        f"Build '{build_name_or_hash}' not found in BrowserStack builds list.\n"
        f"Searched {len(all_builds)} recent builds.\n"
        f"Recent builds:\n  " + "\n  ".join(available_builds[:5])
    )


def delete_failed_sessions(build_id):
    """Delete all failed sessions for a given build ID.
    
    This function now handles multiple hashed build IDs - it will find ALL builds
    with the given name, check all of them for failed sessions, and delete them.

    Args:
        build_id: Build ID in format like "20260412-064121-6903a"
        
    Returns:
        dict with keys: deleted_count, total_failed, failed_deletes, error (if any)
    """
    try:
        # Get ALL hashed build IDs for this build name
        print(f"Finding all hashed build IDs for '{build_id}'...")
        hashed_build_ids = get_all_hashed_build_ids(build_id)
        print(f"\nWill process {len(hashed_build_ids)} hashed build ID(s)")
        print(f"Hashed build IDs: {hashed_build_ids}\n")

        auth = (BS_USERNAME, BS_ACCESS_KEY)

        # Collect ALL failed sessions from ALL hashed build IDs
        all_failed_sessions = []

        for idx, hashed_build_id in enumerate(hashed_build_ids, 1):
            print(f"\n{'='*80}")
            print(f"Processing build {idx}/{len(hashed_build_ids)}: {hashed_build_id}")
            print(f"{'='*80}")

            # Get build info (optional - only show if successful)
            try:
                build_info_url = f"https://api.browserstack.com/automate/builds/{hashed_build_id}.json"
                build_response = requests.get(build_info_url, auth=auth, timeout=30)
                build_response.raise_for_status()
                build_data = build_response.json()
                build_info = build_data.get("automation_build", {})

                # Only print if we have valid build info
                if build_info:
                    print(f"  Build name: {build_info.get('name', 'N/A')}")
                    print(f"  Build status: {build_info.get('status', 'N/A')}")
                    print(f"  Build duration: {build_info.get('duration', 0)}s")
                    
                    # Check if there's a session count in the build info
                    if 'sessions' in build_info:
                        print(f"  Sessions in build metadata: {build_info['sessions']}")
            except Exception:
                # Silently continue - build info is optional
                pass

            # Fetch all sessions for this build with pagination
            # Note: BrowserStack API enforces a max limit of ~100 per request
            # We use pagination to fetch all sessions
            all_sessions = []
            offset = 0
            limit = 100  # BrowserStack API max limit per request
            page_num = 1

            print(f"\n  Fetching all sessions for this build...")
            while True:
                sessions_url = f"https://api.browserstack.com/automate/builds/{hashed_build_id}/sessions.json?limit={limit}&offset={offset}"
                
                response = requests.get(sessions_url, auth=auth, timeout=60)
                response.raise_for_status()
                sessions_page = response.json()

                if not sessions_page:
                    if page_num == 1:
                        print(f"    No sessions found for this build")
                    break

                current_count = len(sessions_page)
                all_sessions.extend(sessions_page)
                print(f"    Page {page_num}: Retrieved {current_count} sessions (total so far: {len(all_sessions)})")

                # If we got fewer than the limit, we've reached the end
                if current_count < limit:
                    break

                offset += limit
                page_num += 1

            sessions_data = all_sessions
            print(f"  ✓ Total sessions fetched: {len(sessions_data)}")

            # Count statuses for debugging
            status_counts = {}
            for session_data in sessions_data:
                session = session_data.get("automation_session", {})
                status = session.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

            print(f"  Status breakdown: {status_counts}")

            # Filter failed sessions (anything that's NOT "passed")
            build_failed_count = 0
            for session_data in sessions_data:
                session = session_data.get("automation_session", {})
                status = session.get("status", "")
                session_name = session.get("name", "Unknown")
                session_id = session.get("hashed_id", "")

                # Consider failed: error, failed, timeout, or empty status
                # Don't delete: passed, running
                if status and status.lower() not in ["passed", "running"]:
                    all_failed_sessions.append({
                        "session_id": session_id,
                        "name": session_name,
                        "status": status,
                        "build_id": hashed_build_id
                    })
                    build_failed_count += 1

            print(f"  Found {build_failed_count} failed sessions in this build")

        # Now delete all failed sessions from all builds
        total_failed = len(all_failed_sessions)
        print(f"\n{'='*80}")
        print(f"SUMMARY: Found {total_failed} total failed sessions across {len(hashed_build_ids)} build(s)")
        print(f"{'='*80}\n")

        if total_failed == 0:
            return {
                "deleted_count": 0,
                "total_failed": 0,
                "failed_deletes": 0,
                "builds_processed": len(hashed_build_ids),
                "message": f"No failed sessions found in {len(hashed_build_ids)} build(s)"
            }

        # Delete each failed session with retry logic
        deleted_count = 0
        failed_deletes = 0

        print(f"Starting deletion of {total_failed} failed sessions...\n")

        for session_info in all_failed_sessions:
            session_id = session_info["session_id"]
            session_name = session_info["name"]
            build_id_short = session_info["build_id"][:20]

            # Try to delete with 3 retries
            delete_url = f"https://api.browserstack.com/automate/sessions/{session_id}.json"
            success = False

            for attempt in range(3):
                try:
                    delete_response = requests.delete(delete_url, auth=auth, timeout=30)
                    if delete_response.status_code == 200:
                        deleted_count += 1
                        print(f"Deleted {deleted_count}/{total_failed}: {session_name[:50]} (build: {build_id_short}...)")
                        success = True
                        break
                    elif delete_response.status_code == 404:
                        # Session already deleted or doesn't exist
                        print(f"Session {session_name[:50]} not found (404), skipping")
                        success = True
                        break
                    elif delete_response.status_code == 429:
                        # Rate limited, wait and retry
                        wait_time = 2 ** attempt  # 1s, 2s, 4s
                        print(f"Rate limited (429), waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        print(f"Failed to delete {session_name[:50]}: HTTP {delete_response.status_code}")
                        if attempt < 2:
                            wait_time = 2 ** attempt
                            time.sleep(wait_time)
                except requests.RequestException as e:
                    print(f"Error deleting {session_name[:50]}: {e}")
                    if attempt < 2:
                        wait_time = 2 ** attempt
                        time.sleep(wait_time)

            if not success:
                failed_deletes += 1
                print(f"Failed to delete after 3 attempts: {session_name[:50]}")

        return {
            "deleted_count": deleted_count,
            "total_failed": total_failed,
            "failed_deletes": failed_deletes,
            "builds_processed": len(hashed_build_ids),
            "hashed_build_ids": hashed_build_ids
        }

    except (ValueError, AttributeError):
        # get_all_hashed_build_ids() failed - likely invalid build_id or build not found
        return {
            "error": f"Build not found in BrowserStack: '{build_id}'. It may be older than all builds searched, or the name doesn't match exactly."
        }
    except requests.HTTPError as e:
        if e.response.status_code == 401 or e.response.status_code == 403:
            return {
                "error": "Authentication failed. Please check your BrowserStack credentials."
            }
        elif e.response.status_code == 404:
            return {
                "error": f"Build not found: {build_id}"
            }
        else:
            return {
                "error": f"HTTP error: {e.response.status_code} - {str(e)}"
            }
    except Exception as e:
        return {
            "error": f"Error processing build: {str(e)}"
        }


def extract_error_details(session):
    """Extract clean error details without stacktrace noise"""
    error_reason = session.get("reason", "Unknown")

    # Clean up the error reason - remove stacktrace
    if error_reason and error_reason != "Unknown":
        # Remove everything after "Stacktrace:" or "Stack:"
        error_reason = re.split(r'\s*Stacktrace:|\s*Stack:', error_reason, flags=re.IGNORECASE)[0]
        # Remove everything after "at " lines (Java/Python stacktrace)
        error_reason = re.split(r'\n\s*at\s+', error_reason)[0]
        # Remove "For documentation on this error" and everything after
        error_reason = re.split(r'For documentation on this error.*', error_reason, flags=re.IGNORECASE)[0]
        # Remove file paths
        error_reason = re.sub(r'\([^)]*\.(py|java|js):\d+\)', '', error_reason)
        # Clean up multiple newlines
        error_reason = re.sub(r'\n{2,}', '\n', error_reason)
        # Trim whitespace
        error_reason = error_reason.strip()

        # Extract just the main error message if it's too long
        if len(error_reason) > 300:
            # Try to get just the first meaningful line
            lines = error_reason.split('\n')
            error_reason = lines[0].strip()

    # Simplify common error messages
    error_simplifications = {
        r'NoSuchElementException.*': 'Element not found on page',
        r'TimeoutException.*': 'Operation timed out',
        r'StaleElementReferenceException.*': 'Element became stale (page changed)',
        r'ElementClickInterceptedException.*': 'Element was blocked by another element',
        r'ElementNotInteractableException.*': 'Element not interactable (hidden or disabled)',
        r'WebDriverException.*': 'Browser communication error',
        r'AssertionError.*': 'Test assertion failed',
    }

    for pattern, simple_msg in error_simplifications.items():
        if re.search(pattern, error_reason, re.IGNORECASE):
            # Keep the simple message but append specific details if short
            match = re.search(r'Message:\s*([^\n]+)', error_reason)
            if match and len(match.group(1)) < 100:
                error_reason = f"{simple_msg}: {match.group(1).strip()}"
            else:
                error_reason = simple_msg
            break

    return error_reason, None  # We no longer return error_message (removed stacktrace display)


@app.route("/", methods=["GET", "POST"])
def index():
    generated_file = None
    error_msg = None
    cleanup_result = None

    if request.method == "POST":
        # Check if this is a cleanup request (build_id) or generate request (session_url)
        build_id_input = request.form.get("build_id")
        session_url = request.form.get("session_url")

        if build_id_input:
            # Cleanup action - delete failed sessions
            print(f"Cleanup requested for build_id: {build_id_input}")
            cleanup_result = delete_failed_sessions(build_id_input)
            if "error" in cleanup_result:
                error_msg = cleanup_result["error"]
                cleanup_result = None
        elif session_url:
            # Generate action - create reproduction page
            session_id, build_id, auth_token = extract_session_info(session_url)
            if not session_id:
                error_msg = "Invalid session URL. Please paste a valid BrowserStack session URL."
            else:
                try:
                    session = fetch_session(session_id, auth_token)
                    logs = fetch_logs(session_id, auth_token)

                    # Get video URL - used directly in template, no download needed
                    video_base64 = None
                    video_url = session.get("video_url", "")

                    # Parse steps (no screenshots needed)
                    steps = parse_steps(logs)
                    error_reason, error_message = extract_error_details(session)

                    # Get test status
                    test_status = session.get("status", "unknown")

                    # Get log URLs from session
                    # BrowserStack session data contains pre-authenticated URLs
                    selenium_logs_url = session.get("logs", "")

                    # For network and console logs, use the public dashboard URL format
                    # which supports auth_token parameter
                    # Use build_id from URL or from session data
                    actual_build_id = build_id or session.get("build_hashed_id", "") or session.get("hashed_id", "")

                    # Fetch build name (Player lib version)
                    current_build_name = fetch_build_name(actual_build_id)

                    # Try to get from session data first (these are pre-authenticated if available)
                    network_logs_url = session.get("har_logs_url", "")
                    console_logs_url = session.get("browser_console_logs_url", "")

                    # If not available and we have build_id and auth_token, construct public URLs
                    if auth_token and actual_build_id:
                        base_public_url = (
                            f"https://automate.browserstack.com/builds/"
                            f"{actual_build_id}/sessions/{session_id}"
                        )
                        if not network_logs_url:
                            network_logs_url = f"{base_public_url}/networklogs?auth_token={auth_token}"
                        if not console_logs_url:
                            console_logs_url = f"{base_public_url}/consolelogs?auth_token={auth_token}"
                    else:
                        # Fallback - these may require login
                        session_base_url = (
                            f"https://api.browserstack.com/automate/sessions/{session_id}"
                        )
                        if not network_logs_url:
                            network_logs_url = f"{session_base_url}/networklogs"
                        if not console_logs_url:
                            console_logs_url = f"{session_base_url}/consolelogs"

                    # Construct BrowserStack session URL for direct access
                    bs_session_url = session_url  # Use the original URL provided by user
                    if not bs_session_url or "auth_token" not in bs_session_url:
                        # Construct URL with auth_token if available
                        if auth_token and actual_build_id:
                            bs_session_url = (
                                f"https://automate.browserstack.com/builds/"
                                f"{actual_build_id}/sessions/{session_id}?auth_token={auth_token}"
                            )
                        else:
                            bs_session_url = (
                                f"https://automate.browserstack.com/builds/"
                                f"{actual_build_id}/sessions/{session_id}"
                            )

                    # Find last successful run of this test
                    test_name = session.get("name", "Unknown Test")
                    last_success = None
                    print(f"Test status: {test_status}")
                    if test_status != "passed":
                        print("Test failed - searching for last successful run...")
                        # Pass build_id so we search same build first
                        last_success = find_last_successful_run(
                            test_name, session_id, actual_build_id
                        )
                        if last_success:
                            print(f"Found last_success: {last_success}")
                        else:
                            print("No last_success found")
                    else:
                        print("Test passed - not searching for last successful run")

                    # Extract EUX BO URL from WalkMe snippet in logs
                    eux_bo_url = extract_eux_bo_url(logs, test_name)

                    # Fetch and filter WalkMe-related network logs
                    print("Fetching WalkMe network logs...")
                    walkme_network_logs = fetch_walkme_network_logs(session_id, auth_token)

                    html_content = render_template_string(
                        HTML_TEMPLATE,
                        test_name=test_name,
                        build_name=current_build_name,
                        browser=session.get("browser", "Unknown"),
                        browser_version=session.get("browser_version", ""),
                        os=session.get("os", "Unknown"),
                        os_version=session.get("os_version", ""),
                        status=session.get("status", "unknown"),
                        duration=session.get("duration", "N/A"),
                        steps=steps,
                        error_reason=error_reason,
                        error_message=error_message,
                        video_url=video_url,
                        network_logs_url=network_logs_url,
                        console_logs_url=console_logs_url,
                        selenium_logs_url=selenium_logs_url,
                        bs_session_url=bs_session_url,
                        last_success=last_success,
                        eux_bo_url=eux_bo_url,
                        walkme_network_logs=walkme_network_logs
                    )

                    # Sanitize test name for filename (remove invalid characters)
                    safe_test_name = re.sub(r'[<>:"/\\|?*\[\]]', '_', test_name)
                    safe_test_name = safe_test_name.strip()[:100]  # Limit length
                    file_name = f"{safe_test_name}.html"
                    with open(file_name, "w", encoding="utf-8") as f:
                        f.write(html_content)

                    generated_file = file_name
                except Exception as e:
                    error_msg = f"Error processing session: {str(e)}"

    # Modern Google-style landing page
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>BS TestReplay</title>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: #f8f9fa;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            .logo {{
                font-size: 48px;
                margin-bottom: 8px;
            }}
            .title {{
                font-size: 32px;
                font-weight: 300;
                color: #202124;
                margin-bottom: 8px;
                text-align: center;
            }}
            .title span {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                font-weight: 600;
            }}
            .subtitle {{
                color: #5f6368;
                font-size: 16px;
                margin-bottom: 32px;
                text-align: center;
            }}
            .search-container {{
                width: 100%;
                max-width: 584px;
                margin-bottom: 24px;
            }}
            .search-box {{
                display: flex;
                align-items: center;
                background: white;
                border: 1px solid #dfe1e5;
                border-radius: 24px;
                padding: 12px 20px;
                box-shadow: 0 1px 6px rgba(32,33,36,0.08);
                transition: all 0.2s ease;
            }}
            .search-box:hover, .search-box:focus-within {{
                box-shadow: 0 1px 6px rgba(32,33,36,0.28);
                border-color: transparent;
            }}
            .search-icon {{
                color: #9aa0a6;
                margin-right: 12px;
                font-size: 20px;
            }}
            .search-input {{
                flex: 1;
                border: none;
                outline: none;
                font-size: 16px;
                color: #202124;
                background: transparent;
            }}
            .search-input::placeholder {{
                color: #9aa0a6;
            }}
            .btn-container {{
                display: flex;
                justify-content: center;
                gap: 12px;
                margin-top: 24px;
            }}
            .btn {{
                background: #f8f9fa;
                border: 1px solid #f8f9fa;
                border-radius: 4px;
                color: #3c4043;
                font-size: 14px;
                padding: 10px 16px;
                cursor: pointer;
                transition: all 0.2s ease;
            }}
            .btn:hover {{
                box-shadow: 0 1px 3px rgba(32,33,36,0.2);
                border-color: #dadce0;
            }}
            .btn-primary {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 12px 24px;
                font-size: 15px;
                font-weight: 500;
                border-radius: 24px;
                cursor: pointer;
            }}
            .btn-primary:hover {{
                box-shadow: 0 2px 8px rgba(102, 126, 234, 0.4);
                transform: translateY(-1px);
            }}
            .btn-primary:disabled {{
                opacity: 0.7;
                cursor: not-allowed;
                transform: none;
            }}
            .loading {{
                display: none;
                align-items: center;
                gap: 10px;
                margin-top: 16px;
                color: #667eea;
                font-size: 14px;
            }}
            .loading.active {{
                display: flex;
                justify-content: center;
            }}
            .spinner {{
                width: 20px;
                height: 20px;
                border: 3px solid #e2e8f0;
                border-top-color: #667eea;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
            }}
            @keyframes spin {{
                to {{ transform: rotate(360deg); }}
            }}
            .result-box {{
                width: 100%;
                max-width: 584px;
                margin-top: 24px;
                padding: 20px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.08);
                animation: slideUp 0.3s ease;
            }}
            @keyframes slideUp {{
                from {{ opacity: 0; transform: translateY(10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            .result-success {{
                border-left: 4px solid #34a853;
            }}
            .result-error {{
                border-left: 4px solid #ea4335;
            }}
            .result-title {{
                font-size: 16px;
                font-weight: 600;
                color: #202124;
                margin-bottom: 12px;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            .result-link {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 500;
                transition: all 0.2s ease;
            }}
            .result-link:hover {{
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
                transform: translateY(-2px);
            }}
            .result-file {{
                color: #5f6368;
                font-size: 13px;
                margin-top: 12px;
            }}
            .error-text {{
                color: #ea4335;
                font-size: 14px;
            }}
            .footer {{
                position: fixed;
                bottom: 20px;
                color: #70757a;
                font-size: 13px;
            }}
            .tips {{
                max-width: 584px;
                margin-top: 32px;
                padding: 16px 20px;
                background: #f0f4ff;
                border-radius: 8px;
                font-size: 13px;
                color: #5f6368;
            }}
            .tips-title {{
                font-weight: 600;
                color: #667eea;
                margin-bottom: 8px;
            }}
            .separator {{
                width: 100%;
                max-width: 584px;
                margin: 48px auto;
                display: flex;
                align-items: center;
                gap: 16px;
            }}
            .separator-line {{
                flex: 1;
                height: 1px;
                background: #dadce0;
            }}
            .separator-text {{
                color: #5f6368;
                font-size: 14px;
                font-weight: 500;
                padding: 6px 16px;
                background: #f8f9fa;
                border-radius: 20px;
                border: 1px solid #dadce0;
            }}
            .btn-cleanup {{
                background: linear-gradient(135deg, #ea4335 0%, #e63946 100%);
                color: white;
                border: none;
                padding: 12px 24px;
                font-size: 15px;
                font-weight: 500;
                border-radius: 24px;
                cursor: pointer;
            }}
            .btn-cleanup:hover {{
                box-shadow: 0 2px 8px rgba(234, 67, 53, 0.4);
                transform: translateY(-1px);
            }}
            .btn-cleanup:disabled {{
                opacity: 0.7;
                cursor: not-allowed;
                transform: none;
            }}
            .cleanup-spinner {{
                width: 20px;
                height: 20px;
                border: 3px solid #e2e8f0;
                border-top-color: #ea4335;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
            }}
            .cleanup-loading {{
                display: none;
                align-items: center;
                gap: 10px;
                margin-top: 16px;
                color: #ea4335;
                font-size: 14px;
            }}
            .cleanup-loading.active {{
                display: flex;
                justify-content: center;
            }}
            .cleanup-result {{
                color: #202124;
                font-size: 14px;
                line-height: 1.6;
            }}
        </style>
    </head>
    <body>
        <div class="logo">🔍</div>
        <h1 class="title"><span>BS</span> TestReplay</h1>
        <p class="subtitle">Convert test sessions into standalone reproduction pages for QA</p>
        
        <form method="post" class="search-container" id="generateForm" onsubmit="showLoading()">
            <div class="search-box">
                <span class="search-icon">🔗</span>
                <input type="text" name="session_url" class="search-input" 
                       placeholder="Paste BrowserStack session URL here..." 
                       autocomplete="off" autofocus required>
            </div>
            <div class="btn-container">
                <button type="submit" class="btn btn-primary" id="submitBtn">Generate Link</button>
            </div>
            <div class="loading" id="loadingIndicator">
                <div class="spinner"></div>
                <span>Fetching session data, downloading video, and extracting frames...</span>
            </div>
        </form>

        {f'''
        <div class="result-box result-success">
            <div class="result-title">✅ Report Generated Successfully!</div>
            <a href="/download/{generated_file}" class="result-link">
                <span>📥</span> Download Page
            </a>
            <p class="result-file">File: {generated_file}</p>
        </div>
        ''' if generated_file else ''}

        {f'''
        <div class="result-box result-error">
            <div class="result-title">❌ Error</div>
            <p class="error-text">{error_msg}</p>
        </div>
        ''' if error_msg and not cleanup_result else ''}

        {f'''
        <div class="result-box result-success">
            <div class="result-title">✅ Cleanup Completed!</div>
            <p class="cleanup-result">
                Deleted <strong>{cleanup_result["deleted_count"]}</strong> of <strong>{cleanup_result["total_failed"]}</strong> failed sessions
                {f'<br><span style="color: #ea4335;">⚠️ {cleanup_result["failed_deletes"]} sessions failed to delete after retries</span>' if cleanup_result.get("failed_deletes", 0) > 0 else ''}
            </p>
        </div>
        ''' if cleanup_result else ''}

        <!-- Separator between two tools -->
        <div class="separator">
            <div class="separator-line"></div>
            <div class="separator-text">OR</div>
            <div class="separator-line"></div>
        </div>

        <!-- Cleanup Failed Sessions Section -->
        <form method="post" class="search-container" id="cleanupForm" onsubmit="showCleanupLoading()">
            <div class="search-box">
                <span class="search-icon">🗑️</span>
                <input type="text" name="build_id" class="search-input" 
                       placeholder="Enter Build Name or Hashed ID (e.g., 20260412-064121-6903a or 910d848...)..." 
                       autocomplete="off" required>
            </div>
            <div class="btn-container">
                <button type="submit" class="btn btn-cleanup" id="cleanupBtn">🗑️ Delete Failed Sessions</button>
            </div>
            <div class="cleanup-loading" id="cleanupLoadingIndicator">
                <div class="cleanup-spinner"></div>
                <span>Finding and deleting failed sessions...</span>
            </div>
        </form>

        <div class="tips">
            <div class="tips-title">💡 Tips</div>
            <strong>Generate Link:</strong> Paste a session URL like: <code>https://automate.browserstack.com/dashboard/v2/sessions/abc123...</code><br>
            <strong>Delete Failed Sessions:</strong> Enter a Build Name like <code>20260412-064121-6903a</code> OR Hashed ID from URL like <code>910d848cde11c50835c0537c3b8899552067f48c</code>
        </div>

        <div class="footer">
            BS TestReplay v{APP_VERSION} • For QA Teams
        </div>

        <script>
            function showLoading() {{
                document.getElementById('submitBtn').disabled = true;
                document.getElementById('submitBtn').textContent = 'Generating...';
                document.getElementById('loadingIndicator').classList.add('active');
            }}
            
            function showCleanupLoading() {{
                document.getElementById('cleanupBtn').disabled = true;
                document.getElementById('cleanupBtn').textContent = '🗑️ Deleting...';
                document.getElementById('cleanupLoadingIndicator').classList.add('active');
            }}
        </script>
    </body>
    </html>
    """


@app.route("/download/<filename>")
def download(filename):
    response = send_file(filename, as_attachment=True)

    # Schedule cleanup of the file after sending
    @response.call_on_close
    def cleanup():
        try:
            if os.path.exists(filename):
                os.remove(filename)
                print(f"Cleaned up file: {filename}")
        except Exception as e:
            print(f"Failed to cleanup file {filename}: {e}")

    return response


def cleanup_temp_files():
    """Clean up any leftover temporary files (mp4, html) in the current directory"""
    try:
        for f in os.listdir('.'):
            # Clean up temp video files
            if f.endswith('.mp4') and f.startswith('tmp'):
                try:
                    os.remove(f)
                    print(f"Cleaned up temp file: {f}")
                except Exception as e:
                    print(f"Failed to cleanup {f}: {e}")
    except Exception as e:
        print(f"Cleanup error: {e}")


if __name__ == "__main__":
    # Clean up any leftover temp files from previous runs
    cleanup_temp_files()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
