use proc_macro2::Span;
use quote::ToTokens;
use regex::Regex;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use syn::visit::Visit;
use syn::{Attribute, Ident, ItemFn, ItemImpl, ItemStruct};

pub fn sha256_id(repo_id: &str, rel_path: &str, qual_symbol: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(repo_id.as_bytes());
    hasher.update(&[0x1f]);
    hasher.update(rel_path.as_bytes());
    hasher.update(&[0x1f]);
    hasher.update(qual_symbol.as_bytes());
    let digest = hasher.finalize();
    format!("{:x}", digest)
}

pub fn merge_doc_comments(attrs: &[Attribute]) -> String {
    let mut out = String::new();
    for attr in attrs {
        let mut added = false;
        // Try structured parsing
        let _ = attr.parse_nested_meta(|meta| {
            if meta.path.is_ident("doc") {
                let lit: syn::LitStr = meta.value()?.parse()?;
                if !out.is_empty() {
                    out.push('\n');
                }
                out.push_str(lit.value().trim());
                added = true;
            }
            Ok(())
        });
        // Fallback regex on token stream for #[doc = "..."]
        if !added && attr.path().is_ident("doc") {
            let ts = attr.to_token_stream().to_string();
            let re = Regex::new("doc\\s*=\\s*\"([^\"]*)\"").unwrap();
            if let Some(c) = re.captures(&ts) {
                if !out.is_empty() {
                    out.push('\n');
                }
                out.push_str(c.get(1).unwrap().as_str());
            }
        }
    }
    out
}

pub fn format_struct_signature(item: &ItemStruct) -> String {
    item.to_token_stream().to_string()
}

pub fn format_impl_signature(item: &ItemImpl) -> String {
    // Only the "impl ... for ... where ..." header
    let mut tokens = String::from("impl ");
    if let Some((bang, path, _for_token)) = &item.trait_ {
        if bang.is_some() {
            tokens.push('!');
        }
        tokens.push_str(&path.to_token_stream().to_string());
        tokens.push_str(" for ");
        tokens.push_str(&item.self_ty.to_token_stream().to_string());
    } else {
        tokens.push_str(&item.self_ty.to_token_stream().to_string());
    }
    if let Some(g) = &item.generics.where_clause {
        tokens.push(' ');
        tokens.push_str(&g.to_token_stream().to_string());
    }
    tokens
}

pub fn format_fn_signature(item: &ItemFn) -> String {
    item.sig.to_token_stream().to_string()
}

pub fn compact_whitespace(s: &str) -> String {
    let re = Regex::new(r"\s+").unwrap();
    re.replace_all(s.trim(), " ").to_string()
}

pub fn strip_comments(src: &str) -> String {
    // Remove // line comments
    let re_line = Regex::new(r"//.*").unwrap();
    let tmp = re_line.replace_all(src, "");
    // Remove /* block */ comments (naive, no nesting)
    let re_block = Regex::new(r"/\*[^*]*\*+(?:[^/*][^*]*\*+)*/").unwrap();
    let tmp2 = re_block.replace_all(&tmp, "");
    tmp2.to_string()
}

pub fn collect_idents(tokens: &proc_macro2::TokenStream) -> String {
    struct V<'a> {
        idents: &'a mut Vec<String>,
    }
    impl<'a, 'ast> Visit<'ast> for V<'a> {
        fn visit_ident(&mut self, i: &'ast Ident) {
            self.idents.push(i.to_string());
        }
    }
    let mut list = Vec::new();
    let mut v = V { idents: &mut list };
    let file: syn::File = syn::parse_quote! { #tokens };
    v.visit_file(&file);
    // Deduplicate while preserving order
    let mut seen = std::collections::HashSet::new();
    list.into_iter()
        .filter(|s| seen.insert(s.clone()))
        .collect::<Vec<_>>()
        .join(" ")
}

pub fn rel_module_path(root: &Path, file: &Path) -> String {
    let rel = pathdiff::diff_paths(file, root).unwrap_or_else(|| file.to_path_buf());
    let mut comps: Vec<String> = Vec::new();
    for comp in rel.components() {
        let s = comp.as_os_str().to_string_lossy().to_string();
        comps.push(s);
    }
    // Remove src/ prefix if present
    let comps = if comps.first().map(|s| s == "src").unwrap_or(false) {
        comps.into_iter().skip(1).collect::<Vec<_>>()
    } else {
        comps
    };
    if comps.is_empty() {
        return "crate".to_string();
    }
    let mut parts = Vec::new();
    for (i, part) in comps.iter().enumerate() {
        if i == comps.len() - 1 {
            // file name
            let p = PathBuf::from(part);
            let stem = p.file_stem().unwrap().to_string_lossy().to_string();
            if stem == "mod" || stem == "lib" || stem == "main" {
                // use directory as module (already added)
            } else {
                parts.push(stem);
            }
        } else {
            parts.push(part.clone());
        }
    }
    if parts.is_empty() {
        "crate".to_string()
    } else {
        format!("crate::{}", parts.join("::"))
    }
}

pub fn span_start_end(span: Span) -> Option<((usize, usize), (usize, usize))> {
    // Returns ((line, col), (line, col)) 1-based if available
    let start = span.start();
    let end = span.end();
    if start.line > 0 && end.line > 0 {
        Some((
            (start.line as usize, start.column as usize),
            (end.line as usize, end.column as usize),
        ))
    } else {
        None
    }
}
