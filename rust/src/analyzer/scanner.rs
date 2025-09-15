use crate::analyzer::model::{OutputPayload, OutputRecord, VectorFields};
use crate::analyzer::util::*;
use anyhow::{Context, Result};
use quote::ToTokens;
use std::fs;
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use syn::spanned::Spanned;
use walkdir::WalkDir;

#[derive(Clone, Debug)]
pub struct AnalyzeConfig {
    pub path: PathBuf,
    pub repo_id: String,
}

fn is_excluded(p: &Path) -> bool {
    let s = p.to_string_lossy();
    s.contains("/target/") || s.ends_with(".generated.rs")
}

pub fn analyze_project(cfg: &AnalyzeConfig) -> Result<Vec<OutputRecord>> {
    let mut out: Vec<OutputRecord> = Vec::new();
    for entry in WalkDir::new(&cfg.path).into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();
        if path.is_dir() || is_excluded(path) {
            continue;
        }
        if path.extension().and_then(|e| e.to_str()) != Some("rs") {
            continue;
        }
        match process_file(&cfg.path, path, &cfg.repo_id) {
            Ok(mut v) => out.append(&mut v),
            Err(e) => {
                eprintln!("[project_analyzer] Skipping {}: {}", path.display(), e);
            }
        }
    }
    Ok(out)
}

fn process_file(root: &Path, file: &Path, repo_id: &str) -> Result<Vec<OutputRecord>> {
    let content =
        fs::read_to_string(file).with_context(|| format!("Failed to read {}", file.display()))?;
    let parsed: syn::File =
        syn::parse_file(&content).with_context(|| format!("Failed to parse {}", file.display()))?;
    let module_path = rel_module_path(root, file);
    let rel_path = pathdiff::diff_paths(file, root)
        .unwrap_or_else(|| file.to_path_buf())
        .to_string_lossy()
        .to_string();

    let mut records = Vec::new();
    for item in parsed.items.iter() {
        match item {
            syn::Item::Struct(s) => {
                let qual = format!("{}::{}", module_path, s.ident);
                let (start, end, text) = locate_item_text(&content, &s.ident.to_string(), "struct");
                let doc = merge_doc_comments(&s.attrs);
                let signature = format_struct_signature(s);
                let identifiers = collect_idents(&s.to_token_stream());
                let code_body = compact_whitespace(&strip_comments(&text));
                let id = sha256_id(repo_id, &rel_path, &qual);
                records.push(OutputRecord {
                    id,
                    vector_fields: VectorFields {
                        signature,
                        identifiers,
                        code_body,
                        doc_comment: doc,
                    },
                    payload: OutputPayload {
                        repo_id: repo_id.to_string(),
                        path: rel_path.clone(),
                        kind: "struct".to_string(),
                        qual_symbol: qual,
                        start_line: start,
                        end_line: end,
                        text,
                    },
                });
            }
            syn::Item::Impl(im) => {
                // Impl block
                let ty = im.self_ty.to_token_stream().to_string();
                let qual = format!("{}::{}", module_path, ty);
                let (_, _, text) = locate_item_text(&content, &ty, "impl");
                let doc = merge_doc_comments(&im.attrs);
                let signature = format_impl_signature(im);
                let identifiers = collect_idents(&im.to_token_stream());
                let code_body = compact_whitespace(&strip_comments(&text));
                let id = sha256_id(repo_id, &rel_path, &qual);
                // Line numbers best-effort: use span if available
                let start_line = im.span().start().line as usize;
                let end_line = im.span().end().line as usize;
                records.push(OutputRecord {
                    id,
                    vector_fields: VectorFields {
                        signature,
                        identifiers,
                        code_body,
                        doc_comment: doc,
                    },
                    payload: OutputPayload {
                        repo_id: repo_id.to_string(),
                        path: rel_path.clone(),
                        kind: "impl".to_string(),
                        qual_symbol: qual.clone(),
                        start_line,
                        end_line,
                        text,
                    },
                });

                // Methods inside impl
                for it in im.items.iter() {
                    if let syn::ImplItem::Fn(m) = it {
                        let m_name = m.sig.ident.to_string();
                        let qual_m = format!("{}::{}::{}", module_path, ty, m_name);
                        let signature = m.sig.to_token_stream().to_string();
                        let identifiers = collect_idents(&m.to_token_stream());
                        let doc = merge_doc_comments(&m.attrs);
                        let text = m.to_token_stream().to_string();
                        let code_body = if let Some(block) = &m.block.stmts.first() {
                            compact_whitespace(&strip_comments(
                                &m.block.to_token_stream().to_string(),
                            ))
                        } else {
                            String::new()
                        };
                        let id = sha256_id(repo_id, &rel_path, &qual_m);
                        let start_line = m.span().start().line as usize;
                        let end_line = m.span().end().line as usize;
                        records.push(OutputRecord {
                            id,
                            vector_fields: VectorFields {
                                signature,
                                identifiers,
                                code_body,
                                doc_comment: doc,
                            },
                            payload: OutputPayload {
                                repo_id: repo_id.to_string(),
                                path: rel_path.clone(),
                                kind: "fn".to_string(),
                                qual_symbol: qual_m,
                                start_line,
                                end_line,
                                text,
                            },
                        });
                    }
                }
            }
            syn::Item::Fn(f) => {
                let qual = format!("{}::{}", module_path, f.sig.ident);
                let signature = format_fn_signature(f);
                let identifiers = collect_idents(&f.to_token_stream());
                let doc = merge_doc_comments(&f.attrs);
                let text = f.to_token_stream().to_string();
                let code_body = match &f.block {
                    b => compact_whitespace(&strip_comments(&b.to_token_stream().to_string())),
                };
                let id = sha256_id(repo_id, &rel_path, &qual);
                let start_line = f.span().start().line as usize;
                let end_line = f.span().end().line as usize;
                records.push(OutputRecord {
                    id,
                    vector_fields: VectorFields {
                        signature,
                        identifiers,
                        code_body,
                        doc_comment: doc,
                    },
                    payload: OutputPayload {
                        repo_id: repo_id.to_string(),
                        path: rel_path.clone(),
                        kind: "fn".to_string(),
                        qual_symbol: qual,
                        start_line,
                        end_line,
                        text,
                    },
                });
            }
            _ => {}
        }
    }
    Ok(records)
}

// Best-effort fallback to get raw-ish text and line numbers using simple search
fn locate_item_text(content: &str, ident: &str, keyword: &str) -> (usize, usize, String) {
    let mut start_line = 1usize;
    let mut end_line = 1usize;
    let mut text = String::new();
    let needle = format!("{} {}", keyword, ident);
    if let Some(pos) = content.find(&needle) {
        start_line = content[..pos].matches('\n').count() + 1;
        // Find end: either ';' or balanced braces { ... }
        let rest = &content[pos..];
        if let Some(sc) = rest.find(';') {
            // assume ends at semicolon when before a '{'
            let brace_pos = rest.find('{');
            if brace_pos.is_none() || sc < brace_pos.unwrap() {
                let frag = &rest[..=sc];
                text = frag.to_string();
                end_line = start_line + frag.matches('\n').count();
                return (start_line, end_line, text);
            }
        }
        // Brace matching
        if let Some(b) = rest.find('{') {
            let mut depth = 0i32;
            let mut i = b;
            let bytes = rest.as_bytes();
            while i < rest.len() {
                match bytes[i] as char {
                    '{' => depth += 1,
                    '}' => {
                        depth -= 1;
                        if depth == 0 {
                            let frag = &rest[..=i];
                            text = frag.to_string();
                            end_line = start_line + frag.matches('\n').count();
                            break;
                        }
                    }
                    _ => {}
                }
                i += 1;
            }
        }
    }
    (start_line, end_line, text)
}

pub fn write_ndjson(records: &[OutputRecord], out: &mut dyn Write) -> Result<()> {
    let mut buf = BufWriter::new(out);
    buf.write_all(b"[")?;
    let mut first = true;
    for r in records {
        if !first {
            buf.write_all(b",")?;
        }
        serde_json::to_writer(&mut buf, r)?;
        first = false;
    }
    buf.write_all(b"]\n")?;
    buf.flush()?;
    Ok(())
}
