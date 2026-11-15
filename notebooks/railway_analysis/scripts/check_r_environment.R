# Standalone R code; run in R/RStudio or with Rscript, not in a Python cell.
# Input: installed R packages. Output: console only. No package installation.
cat("R:", R.version.string, "\n")
cat("Working directory:", getwd(), "\n")
for (package in c("ggplot2", "readr", "ggrepel", "sf", "jsonlite")) {
  installed <- requireNamespace(package, quietly = TRUE)
  cat(package, ":", if (installed) as.character(packageVersion(package)) else "MISSING", "\n")
}
helper <- "C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R"
cat("Skill helper exists:", file.exists(helper), "\n")
cat("Missing packages will be considered only when a plotting step needs them.\n")
