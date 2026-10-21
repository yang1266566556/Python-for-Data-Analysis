# 助手绘图脚本；使用学生已核验结果，不训练模型。
args <- commandArgs(trailingOnly=TRUE)
library(ggplot2)
source("C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R",encoding="UTF-8")
s <- read.csv(file.path(args[1],"q3_summary.csv"))
d <- read.csv(file.path(args[1],"q3_per_class.csv"))
models <- c("LogisticRegression","DecisionTree","KNN","SVC")
labels <- c("逻辑回归","决策树","KNN","SVC")
s$model <- factor(s$model,levels=models,labels=labels)
d$model <- factor(d$model,levels=models,labels=labels)
long <- rbind(data.frame(model=s$model,metric="Accuracy",value=s$accuracy),
              data.frame(model=s$model,metric="macro-F1",value=s$macro_f1))
font <- "Microsoft YaHei"
p <- ggplot(long,aes(model,value,fill=metric)) +
 geom_col(position=position_dodge(0.75),width=0.65) +
 geom_text(aes(label=sprintf("%.4f",value)),position=position_dodge(0.75),vjust=-0.4,size=3,family=font) +
 scale_fill_manual(values=academic_palette("okabe-ito",8)[1:2],name="评价指标") +
 scale_y_continuous(limits=c(0,1),expand=c(0,0)) + labs(x="默认分类器",y="测试集指标值") +
 theme_academic(base_size=10,base_family=font) + theme(legend.position="bottom")
p <- add_figure_context(p,"图3-1 默认分类器的总体表现","同一测试集1200例；未标准化；除随机种子外使用默认参数",
 "单次固定划分，无误差条；结果不能据此判为统计显著差异。",base_size=10)
q <- ggplot(d,aes(factor(class_label),f1,color=model,shape=model)) +
 geom_point(position=position_dodge(0.65),size=2.4) +
 scale_color_manual(values=academic_palette("okabe-ito",8)[1:4],name="分类器") +
 scale_shape_discrete(name="分类器") +
 scale_y_continuous(limits=c(0,1),breaks=seq(0,1,.2)) + labs(x="类别标签",y="测试集逐类F1") +
 theme_academic(base_size=10,base_family=font) + theme(legend.position="bottom")
q <- add_figure_context(q,"图3-2 默认分类器的逐类表现","全部10类；zero_division=0",
 "各类测试样本数不同；点表示本次得分，不表示不确定性区间。",base_size=10)
out <- file.path(args[1],"figures");dir.create(out,showWarnings=FALSE)
for (name in c("q3_overall","q3_per_class")) {
 fig <- if(name=="q3_overall") p else q
 save_academic_plot(fig,file.path(out,paste0(name,".png")),178,112,300)
 ggsave(file.path(out,paste0(name,".pdf")),fig,device=cairo_pdf,width=178,height=112,units="mm",family=font)
}
writeLines(capture.output(sessionInfo()),file.path(out,"r_session.txt"))
