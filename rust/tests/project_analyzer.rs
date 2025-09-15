use regex::Regex;
use rust_copartner::analyzer::{analyze_project, AnalyzeConfig};
use serde_json::Value;
use std::fs;

#[test]
fn emits_valid_ndjson_and_metadata() {
    // Prepare a temporary project using the fixture content
    let dir = tempfile::tempdir().unwrap();
    let src_dir = dir.path().join("src");
    fs::create_dir_all(&src_dir).unwrap();
    let fixture = include_str!("fixtures/point.rs");
    fs::write(src_dir.join("point.rs"), fixture).unwrap();

    let cfg = AnalyzeConfig {
        path: src_dir.clone(),
        repo_id: "test/repo".to_string(),
    };
    let records = analyze_project(&cfg).expect("analyze should succeed");

    assert!(!records.is_empty(), "should produce records");

    // Validate NDJSON by serializing each record
    let mut kinds = std::collections::HashSet::new();
    let hex64 = Regex::new(r"^[0-9a-f]{64}$").unwrap();
    for rec in &records {
        let line = serde_json::to_string(rec).unwrap();
        let _v: Value = serde_json::from_str(&line).unwrap();
        assert!(hex64.is_match(&rec.id), "id must be 64-char hex");
        assert!(
            !rec.vector_fields.signature.is_empty(),
            "signature non-empty"
        );
        // Doc comments exist for items in fixture
        assert!(
            !rec.vector_fields.doc_comment.is_empty(),
            "doc_comment should be populated for annotated items"
        );
        kinds.insert(rec.payload.kind.clone());
    }

    assert!(kinds.contains("struct"));
    assert!(kinds.contains("impl"));
    assert!(kinds.contains("fn"));
}
