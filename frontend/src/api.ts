// API client for the KlarPost backend.

import { LanguageCode } from './i18n';

const BASE_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export interface Deadline {
  date: string;
  description: string;
  confidence: 'low' | 'medium' | 'high';
}

export interface RequiredAction {
  action: string;
  urgency: 'low' | 'medium' | 'high';
  reason: string;
}

export interface AnalysisResult {
  source_language: string;
  target_language: string;
  document_type: string;
  sender: string;
  summary_translated: string;
  simple_explanation_translated: string;
  key_points: string[];
  deadlines: Deadline[];
  required_actions: RequiredAction[];
  risk_level: 'green' | 'yellow' | 'red';
  risk_reason: string;
  german_reply_draft: string;
  reply_draft_explanation_translated: string;
  questions_to_ask: string[];
  uncertainties: string[];
  disclaimer: string;
}

export interface AnalysisRecord {
  id: string;
  device_id: string;
  target_language: string;
  target_language_label: string;
  mime_type: string;
  created_at: string;
  result: AnalysisResult;
}

export interface AnalysisListItem {
  id: string;
  created_at: string;
  target_language: string;
  target_language_label: string;
  document_type: string;
  sender: string;
  risk_level: 'green' | 'yellow' | 'red';
  summary_translated: string;
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  const text = await res.text();
  let body: any = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const msg = (body && body.detail) || (typeof body === 'string' ? body : `HTTP ${res.status}`);
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return body as T;
}

export async function analyzeDocument(params: {
  device_id: string;
  target_language: LanguageCode;
  file_base64: string;
  mime_type: string;
}): Promise<AnalysisRecord> {
  const res = await fetch(`${BASE_URL}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  return jsonOrThrow<AnalysisRecord>(res);
}

export async function listAnalyses(deviceId: string): Promise<AnalysisListItem[]> {
  const res = await fetch(`${BASE_URL}/api/analyses?device_id=${encodeURIComponent(deviceId)}`);
  return jsonOrThrow<AnalysisListItem[]>(res);
}

export async function getAnalysis(id: string, deviceId: string): Promise<AnalysisRecord> {
  const res = await fetch(`${BASE_URL}/api/analyses/${encodeURIComponent(id)}?device_id=${encodeURIComponent(deviceId)}`);
  return jsonOrThrow<AnalysisRecord>(res);
}

export async function deleteAnalysis(id: string, deviceId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/analyses/${encodeURIComponent(id)}?device_id=${encodeURIComponent(deviceId)}`, {
    method: 'DELETE',
  });
  await jsonOrThrow(res);
}

export async function deleteAllAnalyses(deviceId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/analyses?device_id=${encodeURIComponent(deviceId)}`, {
    method: 'DELETE',
  });
  await jsonOrThrow(res);
}
