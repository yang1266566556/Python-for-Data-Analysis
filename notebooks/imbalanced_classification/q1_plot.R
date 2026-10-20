# 问题1—绘图代码（R，不在Python单元直接执行）｜v1.0
# 前置：Python已生成 results/class_distribution.csv。
# 调用方式：Rscript --vanilla --encoding=UTF-8 q1_plot.R "本次运行目录"
# 图表库参考：已定位的 chapter7/7.4.2 柱状图示例；仅借鉴图层和轴处理，不运行书中数据或安装代码。
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1L) stop("Provide exactly one run directory")
run_dir <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)
for (pkg in c("ggplot2", "ragg", "systemfonts")) {
  if (!requireNamespace(pkg, quietly = TRUE)) stop(paste("Missing package:", pkg))
}
library(ggplot2)
source("C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R", encoding = "UTF-8")
font_family <- "Microsoft YaHei"
stopifnot(font_family %in% systemfonts::system_fonts()$family)

# 问题1—绘图核心：只读取真实数据，验证全部10类及占比口径。
distribution <- read.csv(file.path(run_dir, "results/class_distribution.csv"), fileEncoding = "UTF-8-BOM")
d <- distribution[distribution$split == "train", ]
d <- d[order(d$class_label), ]
stopifnot(nrow(d) == 10L, identical(as.integer(d$class_label), 0:9), all(d$count > 0))
stopifnot(all(abs(d$proportion - d$count / sum(d$count)) < 1e-10))
d$label <- factor(d$class_label, levels = 0:9)
d$bar_text <- sprintf("%d\n(%.2f%%)", d$count, 100 * d$proportion)
plot <- ggplot(d, aes(x = label, y = count, fill = "训练集")) +
  geom_col(width = 0.7) +
  geom_text(aes(label = bar_text), vjust = -0.3, size = 3, family = font_family, lineheight = 1.1) +
  scale_fill_manual(values = c("训练集" = academic_palette("okabe-ito", 8)[1]), name = "数据子集") +
  scale_y_continuous(expand = expansion(mult = c(0, 0.18))) +
  labs(x = "类别标签", y = "样本数量（个）") +
  theme_academic(base_size = 10, base_family = font_family) +
  theme(legend.position = "bottom", plot.margin = margin(8, 12, 8, 8))
# 作业明确要求图内标题，使用技能的带说明版本；不另交付无标题图。
plot <- add_figure_context(
  plot, title = "图1-1 训练集标签分布",
  subtitle = sprintf("训练集 n = %d；10个类别；分层划分后的实际计数", sum(d$count)),
  caption = "柱高为样本数量；括号内为训练集占比。此图不反映分类器性能。", base_size = 10
)

# 辅助导出：清晰PNG用于报告，矢量PDF用于保真保存，不是最终作业PDF。
figure_dir <- file.path(run_dir, "figures")
dir.create(figure_dir, recursive = TRUE, showWarnings = FALSE)
save_academic_plot(plot, file.path(figure_dir, "q1_train_distribution.png"),
                   width_mm = 178, height_mm = 118, dpi = 300)
if (!capabilities("cairo")) stop("Cairo PDF device is unavailable")
ggsave(file.path(figure_dir, "q1_train_distribution.pdf"), plot, device = cairo_pdf,
       width = 178, height = 118, units = "mm", family = font_family, bg = "white")
writeLines(capture.output(sessionInfo()), file.path(run_dir, "results/r_session.txt"))
write.csv(d[, c("class_label", "count", "proportion")],
          file.path(run_dir, "results/r_plot_data_check.csv"), row.names = FALSE)
cat("R绘图完成：训练集10类计数与占比核验通过。\n")
cat("PNG/PDF：", figure_dir, "\n")
