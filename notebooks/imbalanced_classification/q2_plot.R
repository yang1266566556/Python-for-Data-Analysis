# 助手使用的可复现绘图脚本；学生无需运行R。
# 输入目录包含q2_per_class.csv、q2_averages.csv；第二参数为数据来源说明。
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 2)
library(ggplot2)
source("C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R", encoding="UTF-8")
d <- read.csv(file.path(args[1], "q2_per_class.csv"), fileEncoding="UTF-8-BOM")
a <- read.csv(file.path(args[1], "q2_averages.csv"), fileEncoding="UTF-8-BOM")
stopifnot(nrow(d) == 10, identical(as.integer(d$class_label), 0:9), nrow(a) == 3)
metrics <- c("precision", "recall", "f1")
long <- do.call(rbind, lapply(metrics, function(m) {
  rbind(data.frame(category=as.character(d$class_label), metric=m, value=d[[m]], panel="逐类指标（测试集）"),
        data.frame(category=a$average, metric=m, value=a[[m]], panel="平均方式（测试集）"))
}))
long$category <- factor(long$category, levels=c(as.character(0:9), "macro", "micro", "weighted"))
long$metric <- factor(long$metric, levels=metrics, labels=c("Precision", "Recall", "F1"))
long$panel <- factor(long$panel, levels=c("逐类指标（测试集）", "平均方式（测试集）"))
font <- "Microsoft YaHei"
stopifnot(font %in% systemfonts::system_fonts()$family)
p <- ggplot(long, aes(category, value, fill=metric)) +
  geom_col(position=position_dodge(width=0.78), width=0.72) +
  geom_text(aes(label=ifelse(value > 0, sprintf("%.3f",value), "")),
            position=position_dodge(width=0.78), vjust=-0.35, size=2.5, family=font) +
  facet_wrap(~panel, ncol=1, scales="free_x") +
  scale_fill_manual(values=academic_palette("okabe-ito",8)[1:3], name="评价指标") +
  scale_y_continuous(limits=c(0,1.12), breaks=c(0,0.25,0.5,0.75,1), expand=c(0,0)) +
  labs(x="类别标签 / 平均方式", y="指标值（0—1）") +
  theme_academic(base_size=10,base_family=font) +
  theme(legend.position="bottom", panel.spacing=grid::unit(8,"mm"), strip.text=element_text(hjust=0))
p <- add_figure_context(p, "图2-1 常数预测的逐类指标与平均指标", args[2],
                        "全部预测为训练集多数类0；类别1—9指标均为0；zero_division=0。", base_size=10)
save_academic_plot(p,file.path(args[1],"q2_constant_metrics.png"),width_mm=178,height_mm=155,dpi=300)
ggsave(file.path(args[1],"q2_constant_metrics.pdf"),p,device=cairo_pdf,
       width=178,height=155,units="mm",family=font,bg="white")
writeLines(capture.output(sessionInfo()),file.path(args[1],"r_session.txt"))
cat("Q2 figure exported from supplied CSV.\n")
