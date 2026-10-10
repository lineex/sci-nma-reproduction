# Doing Meta-Analysis in R integration scaffold
# This script is a controlled starting point, not a substitute for the
# approved protocol or the completed r_meta_analysis_plan.json.

options(stringsAsFactors = FALSE)

plan_path <- "analysis/r_meta_analysis_plan.json"
input_path <- "data/locked_input_snapshot.csv"
session_path <- "verification/r_session_info.txt"
diagnostic_dir <- "verification/r_diagnostics"
result_dir <- "results"

dir.create(dirname(session_path), recursive = TRUE, showWarnings = FALSE)
dir.create(diagnostic_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(result_dir, recursive = TRUE, showWarnings = FALSE)

`%||%` <- function(x, y) if (is.null(x) || !nzchar(as.character(x))) y else x

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  stop("Install jsonlite in renv before running this scaffold.")
}
plan <- jsonlite::fromJSON(plan_path, simplifyVector = FALSE)
required_plan <- c(
  "primary_estimand", "effect_size_calculation", "pooling", "heterogeneity",
  "moderators", "dependency", "small_study_effects", "diagnostics", "software"
)
missing_plan <- setdiff(required_plan, names(plan))
if (length(missing_plan) > 0L) {
  stop("The R meta-analysis plan is incomplete: ", paste(missing_plan, collapse = ", "))
}

writeLines(capture.output(sessionInfo()), session_path)
seed_value <- suppressWarnings(
  as.integer(plan$software$seed_or_deterministic_rationale %||% "20261011")
)
if (is.na(seed_value)) {
  seed_value <- 20261011L
  message("No numeric seed was supplied; using the documented fallback seed 20261011.")
}
set.seed(seed_value)

if (!file.exists(input_path)) {
  stop("Create the locked input snapshot at ", input_path,
       " after extraction and eligibility approval.")
}
dat <- utils::read.csv(input_path, check.names = FALSE)

# 1. Effect-size calculation
# Keep one row per estimand and bind every conversion to a report/page/table
# locator. Use metafor::escalc or meta::metabin/metacont/metagen only after
# the plan has declared the input columns, direction, and missing-data rule.
#
# Example patterns:
#   metafor::escalc(measure = "RR", ai = events_t, bi = non_events_t,
#                   ci = events_c, di = non_events_c, data = dat)
#   meta::metacont(n.e, mean.e, sd.e, n.c, mean.c, sd.c, sm = "SMD",
#                  method.smd = "Hedges")
#   meta::metagen(TE, seTE, sm = "RR", common = FALSE, random = TRUE,
#                 method.tau = "REML", hakn = TRUE, prediction = TRUE)

if (!requireNamespace("meta", quietly = TRUE) ||
    !requireNamespace("metafor", quietly = TRUE)) {
  stop("Install the protocol-declared meta and metafor versions in renv.")
}

# 2. Primary model
# Fit only the declared measure/model/estimator. Save the complete model
# object, a tidy result table, tau^2/I^2/Q/prediction interval, and warnings.

# 3. Diagnostics
# Run the prespecified leave-one-out, influence, Baujat, GOSH, funnel, and
# conditional small-study-effect checks. Diagnostics inform interpretation;
# they do not trigger automatic study deletion.

# 4. Moderators
# Run only protocol-prespecified subgroup interactions or meta-regression.
# Enforce the declared minimum studies per parameter and report residual
# heterogeneity and the ecological interpretation limitation.

# 5. Network meta-analysis
# When plan$network_meta_analysis$planned is TRUE, use netmeta or the declared
# Bayesian engine. Check connectivity, transitivity, global/local inconsistency,
# multi-arm covariance, ranking uncertainty, and the assumption-failure plan.

# 6. Release artifacts
# Write result tables, diagnostic files, warnings, deviations, and hashes.
# The stage ledger remains the release authority.
message("Scaffold validated. Complete the declared analysis sections before synthesis release.")
