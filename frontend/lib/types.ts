export type DatasetMetadata = {
  dataset_id: string;
  dataset_type: string;
  path: string;
  row_count: number;
  columns: string[];
  source: string;
  metadata: Record<string, unknown>;
};

export type TimelineEvent = {
  id: string;
  title: string;
  description?: string | null;
  stage: string;
  progress: number;
  created_at: string;
};

export type Evidence = {
  id: string;
  investigator: string;
  rule: string;
  summary: string;
  record_ids: string[];
  metrics: Record<string, unknown>;
  confidence: number;
  estimated_amount: number;
};

export type CaseFile = {
  id: string;
  title: string;
  confidence: number;
  evidence: Evidence[];
  root_cause?: string | null;
  estimated_monthly_loss: number;
  estimated_annual_loss: number;
  recommendation?: string | null;
  priority: number;
};

export type Recommendation = {
  id: string;
  title: string;
  description: string;
  priority: number;
  expected_monthly_impact: number;
  related_case_file_ids: string[];
};

export type InvestigationReport = {
  investigation_id: string;
  status: string;
  confidence: number;
  estimated_monthly_loss: number;
  estimated_annual_loss: number;
  investigation_plan: { investigator: string; status: string; priority: number }[];
  datasets: DatasetMetadata[];
  case_files: CaseFile[];
  recommendations: Recommendation[];
  executive_summary?: {
    headline: string;
    summary: string;
    primary_root_causes: string[];
    highest_priority_actions: string[];
    limitations: string[];
  } | null;
  timeline: TimelineEvent[];
};
