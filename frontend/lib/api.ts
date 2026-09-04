import type { DatasetMetadata, InvestigationReport } from "@/lib/types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "The request could not be completed.");
  }
  return response.json() as Promise<T>;
}

export async function uploadDataset(file: File, datasetType: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("dataset_type", datasetType);
  return request<{ dataset: DatasetMetadata }>("/datasets/upload", { method: "POST", body: form });
}

export function createInvestigation(datasets: DatasetMetadata[], investigationId?: string) {
  return request<InvestigationReport>("/investigations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ datasets, investigation_id: investigationId || null })
  });
}

export function getInvestigation(investigationId: string) {
  return request<InvestigationReport>(`/investigations/${investigationId}`);
}

export function listInvestigations() {
  return request<InvestigationReport[]>("/investigations");
}
