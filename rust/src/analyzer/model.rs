use serde::Serialize;

#[derive(Serialize, Debug, Clone)]
pub struct VectorFields {
    pub signature: String,
    pub identifiers: String,
    pub code_body: String,
    pub doc_comment: String,
}

#[derive(Serialize, Debug, Clone)]
pub struct OutputPayload {
    pub repo_id: String,
    pub path: String,
    pub kind: String,
    pub qual_symbol: String,
    pub start_line: usize,
    pub end_line: usize,
    pub text: String,
}

#[derive(Serialize, Debug, Clone)]
pub struct OutputRecord {
    pub id: String,
    pub vector_fields: VectorFields,
    pub payload: OutputPayload,
}
