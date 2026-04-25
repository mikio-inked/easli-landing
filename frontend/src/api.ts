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

export type Category =
  | 'tax'
  | 'insurance'
  | 'rent'
  | 'bank'
  | 'health'
  | 'government'
  | 'court'
  | 'utilities'
  | 'telecom'
  | 'work'
  | 'education'
  | 'other';

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
  category: Category;
  scam_warning: boolean;
  scam_reason: string;
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
  category: Category;
  scam_warning: boolean;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  off_topic: boolean;
  created_at: string;
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

export interface AnalyzePage {
  file_base64: string;
  mime_type: string;
}

export async function analyzeDocument(params: {
  device_id: string;
  target_language: LanguageCode;
  pages: AnalyzePage[];
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

export async function listChatMessages(analysisId: string, deviceId: string): Promise<ChatMessage[]> {
  const res = await fetch(
    `${BASE_URL}/api/analyses/${encodeURIComponent(analysisId)}/messages?device_id=${encodeURIComponent(deviceId)}`
  );
  return jsonOrThrow<ChatMessage[]>(res);
}

export async function sendChatMessage(
  analysisId: string,
  deviceId: string,
  message: string
): Promise<ChatMessage> {
  const res = await fetch(`${BASE_URL}/api/analyses/${encodeURIComponent(analysisId)}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_id: deviceId, message }),
  });
  return jsonOrThrow<ChatMessage>(res);
}

export async function clearChatMessages(analysisId: string, deviceId: string): Promise<void> {
  const res = await fetch(
    `${BASE_URL}/api/analyses/${encodeURIComponent(analysisId)}/messages?device_id=${encodeURIComponent(deviceId)}`,
    { method: 'DELETE' }
  );
  await jsonOrThrow(res);
}
