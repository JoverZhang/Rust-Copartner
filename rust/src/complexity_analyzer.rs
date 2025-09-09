use anyhow::{Context, Result};
use syn::{visit::Visit, *};

#[derive(Debug, Clone)]
pub struct FunctionComplexity {
    pub name: String,
    pub cyclomatic_complexity: usize,
    pub cognitive_complexity: usize,
    pub line_count: usize,
    pub parameter_count: usize,
    pub return_complexity: ComplexityRating,
    pub details: ComplexityDetails,
}

#[derive(Debug, Clone, Default)]
pub struct ComplexityDetails {
    pub if_statements: usize,
    pub match_arms: usize,
    pub loops: usize,
    pub nested_functions: usize,
    pub function_calls: usize,
    pub max_nesting_depth: usize,
    // Advanced analysis features
    pub function_call_chain: Vec<String>,
    pub macro_invocations: Vec<String>,
    pub module_dependencies: Vec<String>,
    pub unsafe_blocks: usize,
    pub generic_parameters: usize,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ComplexityRating {
    Low,    // 1-5
    Medium, // 6-10
    High,   // 11-20
    VeryHigh, // 21+
}

impl ComplexityRating {
    fn from_score(score: usize) -> Self {
        match score {
            1..=5 => Self::Low,
            6..=10 => Self::Medium,
            11..=20 => Self::High,
            _ => Self::VeryHigh,
        }
    }
}

pub struct ComplexityAnalyzer;

impl ComplexityAnalyzer {
    pub fn analyze_file(content: &str) -> Result<Vec<FunctionComplexity>> {
        let syntax = syn::parse_file(content)
            .context("Failed to parse Rust file")?;
        
        let mut analyzer = FunctionVisitor::default();
        analyzer.visit_file(&syntax);
        
        Ok(analyzer.functions)
    }
    
    pub fn analyze_function(func: &ItemFn) -> FunctionComplexity {
        let mut visitor = ComplexityVisitor::default();
        visitor.visit_item_fn(func);
        
        let cyclomatic = visitor.calculate_cyclomatic_complexity();
        let cognitive = visitor.calculate_cognitive_complexity();
        
        FunctionComplexity {
            name: func.sig.ident.to_string(),
            cyclomatic_complexity: cyclomatic,
            cognitive_complexity: cognitive,
            line_count: visitor.line_count,
            parameter_count: func.sig.inputs.len(),
            return_complexity: ComplexityRating::from_score(cyclomatic),
            details: visitor.details,
        }
    }
}

#[derive(Default)]
struct FunctionVisitor {
    functions: Vec<FunctionComplexity>,
}

impl<'ast> Visit<'ast> for FunctionVisitor {
    fn visit_item_fn(&mut self, func: &'ast ItemFn) {
        let complexity = ComplexityAnalyzer::analyze_function(func);
        self.functions.push(complexity);
        
        // Continue visiting nested functions
        syn::visit::visit_item_fn(self, func);
    }
    
    fn visit_impl_item_fn(&mut self, func: &'ast ImplItemFn) {
        // Handle methods in impl blocks
        let item_fn = ItemFn {
            attrs: func.attrs.clone(),
            vis: func.vis.clone(),
            sig: func.sig.clone(),
            block: Box::new(func.block.clone()),
        };
        let complexity = ComplexityAnalyzer::analyze_function(&item_fn);
        self.functions.push(complexity);
        
        syn::visit::visit_impl_item_fn(self, func);
    }
}

#[derive(Default)]
struct ComplexityVisitor {
    details: ComplexityDetails,
    nesting_depth: usize,
    line_count: usize,
}

impl ComplexityVisitor {
    fn calculate_cyclomatic_complexity(&self) -> usize {
        // McCabe cyclomatic complexity = edges - nodes + 2
        // Simplified calculation: 1 + number of decision points
        1 + self.details.if_statements 
          + self.details.match_arms 
          + self.details.loops
    }
    
    fn calculate_cognitive_complexity(&self) -> usize {
        // Cognitive complexity considers nesting depth and unsafe blocks
        let base = self.details.if_statements + self.details.loops + self.details.match_arms;
        let nesting_penalty = self.details.max_nesting_depth * 2;
        let unsafe_penalty = self.details.unsafe_blocks * 3; // unsafe blocks increase cognitive burden
        base + nesting_penalty + unsafe_penalty
    }
    
    fn enter_nesting(&mut self) {
        self.nesting_depth += 1;
        if self.nesting_depth > self.details.max_nesting_depth {
            self.details.max_nesting_depth = self.nesting_depth;
        }
    }
    
    fn exit_nesting(&mut self) {
        self.nesting_depth = self.nesting_depth.saturating_sub(1);
    }
    
    fn collect_use_path(&mut self, tree: &UseTree, path_parts: &mut Vec<String>) {
        match tree {
            UseTree::Path(use_path) => {
                path_parts.push(use_path.ident.to_string());
                self.collect_use_path(&use_path.tree, path_parts);
            }
            UseTree::Name(use_name) => {
                path_parts.push(use_name.ident.to_string());
                let full_path = path_parts.join("::");
                self.details.module_dependencies.push(full_path);
            }
            UseTree::Group(use_group) => {
                for item in &use_group.items {
                    let mut new_path = path_parts.clone();
                    self.collect_use_path(item, &mut new_path);
                }
            }
            _ => {}
        }
    }
}

impl<'ast> Visit<'ast> for ComplexityVisitor {
    fn visit_expr_if(&mut self, expr: &'ast ExprIf) {
        self.details.if_statements += 1;
        self.enter_nesting();
        syn::visit::visit_expr_if(self, expr);
        self.exit_nesting();
    }
    
    fn visit_expr_match(&mut self, expr: &'ast ExprMatch) {
        // Each match expression counts as a decision point, each arm adds complexity
        self.details.match_arms += expr.arms.len();
        self.enter_nesting();
        syn::visit::visit_expr_match(self, expr);
        self.exit_nesting();
    }
    
    fn visit_expr_while(&mut self, expr: &'ast ExprWhile) {
        self.details.loops += 1;
        self.enter_nesting();
        syn::visit::visit_expr_while(self, expr);
        self.exit_nesting();
    }
    
    fn visit_expr_for_loop(&mut self, expr: &'ast ExprForLoop) {
        self.details.loops += 1;
        self.enter_nesting();
        syn::visit::visit_expr_for_loop(self, expr);
        self.exit_nesting();
    }
    
    fn visit_expr_loop(&mut self, expr: &'ast ExprLoop) {
        self.details.loops += 1;
        self.enter_nesting();
        syn::visit::visit_expr_loop(self, expr);
        self.exit_nesting();
    }
    
    fn visit_expr_call(&mut self, expr: &'ast ExprCall) {
        self.details.function_calls += 1;
        
        // Extract function call names
        if let Expr::Path(path_expr) = &*expr.func {
            if let Some(segment) = path_expr.path.segments.last() {
                let func_name = segment.ident.to_string();
                self.details.function_call_chain.push(func_name);
            }
        }
        
        syn::visit::visit_expr_call(self, expr);
    }
    
    fn visit_expr_macro(&mut self, expr: &'ast ExprMacro) {
        // Record macro invocations
        let macro_name = expr.mac.path.segments
            .iter()
            .map(|s| s.ident.to_string())
            .collect::<Vec<_>>()
            .join("::");
        self.details.macro_invocations.push(macro_name);
        
        syn::visit::visit_expr_macro(self, expr);
    }
    
    fn visit_expr_unsafe(&mut self, expr: &'ast ExprUnsafe) {
        self.details.unsafe_blocks += 1;
        self.enter_nesting();
        syn::visit::visit_expr_unsafe(self, expr);
        self.exit_nesting();
    }
    
    fn visit_use_tree(&mut self, use_tree: &'ast UseTree) {
        // Collect module dependencies
        match use_tree {
            UseTree::Path(use_path) => {
                let mut path_parts = vec![use_path.ident.to_string()];
                self.collect_use_path(&use_path.tree, &mut path_parts);
            }
            UseTree::Name(use_name) => {
                self.details.module_dependencies.push(use_name.ident.to_string());
            }
            UseTree::Group(use_group) => {
                for item in &use_group.items {
                    self.visit_use_tree(item);
                }
            }
            _ => {}
        }
        
        syn::visit::visit_use_tree(self, use_tree);
    }
    
    fn visit_item_fn(&mut self, func: &'ast ItemFn) {
        self.details.nested_functions += 1;
        
        // Analyze generic parameters
        self.details.generic_parameters += func.sig.generics.params.len();
        
        syn::visit::visit_item_fn(self, func);
    }
}

impl std::fmt::Display for ComplexityRating {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Low => write!(f, "Low"),
            Self::Medium => write!(f, "Medium"),
            Self::High => write!(f, "High"),
            Self::VeryHigh => write!(f, "Very High"),
        }
    }
}

impl std::fmt::Display for FunctionComplexity {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, 
            "Function: {}\n  Cyclomatic Complexity: {}\n  Cognitive Complexity: {}\n  Lines: {}\n  Parameters: {}\n  Rating: {}",
            self.name, 
            self.cyclomatic_complexity,
            self.cognitive_complexity,
            self.line_count,
            self.parameter_count,
            self.return_complexity
        )
    }
}