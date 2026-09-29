/**
 * Yojana Saathi — Centralized API Client Layer
 * Phase 9: Unified backend data access, error normalization, and case session handling.
 */

class YojanaAPI {
  constructor(baseUrl = '') {
    this.baseUrl = baseUrl;
  }

  async _request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = options.headers || {};

    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    try {
      const response = await fetch(url, { ...options, headers });
      const contentType = response.headers.get('content-type') || '';

      if (!response.ok) {
        let errorDetail = 'Request failed';
        if (contentType.includes('application/json')) {
          const errData = await response.json();
          errorDetail = errData.detail || errData.message || JSON.stringify(errData);
        } else {
          errorDetail = await response.text();
        }
        throw new Error(errorDetail || `HTTP ${response.status}`);
      }

      if (contentType.includes('application/json')) {
        return await response.json();
      } else if (contentType.includes('application/pdf')) {
        return await response.blob();
      }
      return await response.text();
    } catch (err) {
      console.error(`API Error [${endpoint}]:`, err);
      throw err;
    }
  }

  // --- Case Management ---
  async createCase(goal = "Identify applicable welfare schemes and orchestrate readiness", candidateSchemes = []) {
    return this._request('/api/cases', {
      method: 'POST',
      body: JSON.stringify({ goal, candidate_schemes: candidateSchemes }),
    });
  }

  async getCase(caseId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}`);
  }

  // --- Messaging & Agent Chat ---
  async sendMessage(caseId, message) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/messages`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  }

  async getActivityLog(caseId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/activity`);
  }

  async getNextAgentQuestion(caseId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/agent/next-question`);
  }

  // --- Citizen Profile & Confirmation ---
  async getProfile(caseId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/profile`);
  }

  async confirmProfile(caseId, expectedVersion = null) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/profile/confirm`, {
      method: 'POST',
      body: JSON.stringify({ expected_version: expectedVersion }),
    });
  }

  async rejectProfile(caseId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/profile/reject`, {
      method: 'POST',
    });
  }

  async editProfile(caseId, field, value, autoConfirm = false) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/profile/edit`, {
      method: 'POST',
      body: JSON.stringify({ field, value, auto_confirm: autoConfirm }),
    });
  }

  async getProfileFields() {
    return this._request('/api/profile/fields');
  }

  // --- Schemes & Evaluation ---
  async getSchemesCatalog() {
    return this._request('/api/schemes/catalog');
  }

  async evaluateSchemes(caseId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/schemes/evaluate`, {
      method: 'POST',
    });
  }

  async getCaseSchemes(caseId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/schemes`);
  }

  async selectSchemes(caseId, schemeIds) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/schemes/select`, {
      method: 'POST',
      body: JSON.stringify({ selected_scheme_ids: schemeIds }),
    });
  }

  // --- Applications ---
  async getApplications(caseId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications`);
  }

  async getApplication(caseId, applicationId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}`);
  }

  async activateApplication(caseId, applicationId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/activate`, {
      method: 'POST',
    });
  }

  async updateApplicationStatus(caseId, applicationId, status) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/status`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    });
  }

  // --- Documents & Readiness ---
  async getApplicationDocuments(caseId, applicationId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/documents`);
  }

  async uploadDocument(caseId, applicationId, file, documentType) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/documents`, {
      method: 'POST',
      body: formData,
    });
  }

  async processDocument(caseId, applicationId, documentId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/documents/${encodeURIComponent(documentId)}/process`, {
      method: 'POST',
    });
  }

  async resolveDiscrepancy(caseId, applicationId, documentId, resolution, resolvedValue = null) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/documents/${encodeURIComponent(documentId)}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolution, resolved_value: resolvedValue }),
    });
  }

  async getReadiness(caseId, applicationId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/readiness`);
  }

  // --- Pre-Submission & Handoff ---
  async getPreSubmissionVerification(caseId, applicationId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/pre-submission-verification`);
  }

  async generateReferenceSheet(caseId, applicationId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/reference-sheet`, {
      method: 'POST',
    });
  }

  async generateDossier(caseId, applicationId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/dossier`, {
      method: 'POST',
    });
  }

  async generateHandoffPackage(caseId, applicationId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/handoff-package`, {
      method: 'POST',
    });
  }

  async getHandoffPackage(caseId, applicationId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/handoff-package`);
  }

  getArtifactDownloadUrl(caseId, applicationId, packageId, artifact) {
    return `/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/handoff-package/${encodeURIComponent(packageId)}/${encodeURIComponent(artifact)}`;
  }

  // --- Rejection & Recovery ---
  async claimRejection(caseId, applicationId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/rejection`, {
      method: 'POST',
    });
  }

  async addRejectionEvidence(caseId, applicationId, eventId, evidenceType, noticeText, rejectionCode) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/rejection/${encodeURIComponent(eventId)}/evidence`, {
      method: 'POST',
      body: JSON.stringify({
        evidence_type: evidenceType,
        official_notice_text: noticeText,
        rejection_code: rejectionCode,
      }),
    });
  }

  async decodeRejection(caseId, applicationId, eventId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/rejection/${encodeURIComponent(eventId)}/decode`, {
      method: 'POST',
    });
  }

  async getRecoveryState(caseId, applicationId) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/recovery`);
  }

  async executeRecoveryAction(caseId, applicationId, eventId, action, evidenceNote = null) {
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/applications/${encodeURIComponent(applicationId)}/rejection/${encodeURIComponent(eventId)}/recovery/action`, {
      method: 'POST',
      body: JSON.stringify({ action, evidence_note: evidenceNote }),
    });
  }

  // --- Voice & Languages ---
  async getSupportedLanguages() {
    return this._request('/api/voice/languages');
  }

  async uploadVoice(caseId, audioBlob, language = 'en', turnId = null) {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'voice_recording.wav');
    formData.append('language', language);
    if (turnId) formData.append('turn_id', turnId);
    return this._request(`/api/cases/${encodeURIComponent(caseId)}/voice`, {
      method: 'POST',
      body: formData,
    });
  }
}

// Global API singleton
window.api = new YojanaAPI();
