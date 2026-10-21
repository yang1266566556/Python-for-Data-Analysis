# 助手使用真实重复记录生成质量图和计时图，学生无需运行R。
args <- commandArgs(trailingOnly=TRUE)
library(ggplot2)
source("C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R",encoding="UTF-8")
s <- read.csv(file.path(args[1],"q4_summary.csv"))
model_order <- c("LogisticRegression","DecisionTree","KNN","SVC")
s$model <- factor(s$model,levels=model_order,labels=c("逻辑回归","决策树","KNN","SVC"))
s$setting <- factor(s$setting,levels=c("raw","standardized"),labels=c("原始特征","标准化"))
quality <- do.call(rbind,lapply(c("accuracy","macro_f1"),function(m) data.frame(
 model=s$model,setting=s$setting,metric=if(m=="accuracy")"Accuracy" else "macro-F1",
 mean=s[[paste0(m,"_mean")]],sd=s[[paste0(m,"_std")]])))
font <- "Microsoft YaHei"
q <- ggplot(quality,aes(model,mean,fill=setting)) +
 geom_col(position=position_dodge(0.75),width=0.65) +
 geom_text(aes(label=sprintf("%.4f",mean)),position=position_dodge(0.75),vjust=-.4,size=3,family=font) +
 facet_wrap(~metric,ncol=1) + scale_y_continuous(limits=c(0,1),expand=c(0,0)) +
 scale_fill_manual(values=academic_palette("okabe-ito",8)[1:2],name="特征处理") +
 labs(x="分类器",y="测试集指标均值") + theme_academic(base_size=10,base_family=font) +
 theme(legend.position="bottom")
q <- add_figure_context(q,"图4-1 标准化前后的预测质量","同一数据划分与模型参数；每设置重复5次",
 "各设置的5次预测相同，指标标准差为0；这不表示泛化没有不确定性。",base_size=10)
timing <- do.call(rbind,lapply(c("fit_seconds","predict_seconds"),function(m) data.frame(
 model=s$model,setting=s$setting,phase=if(m=="fit_seconds")"训练：含标准化拟合与转换" else "预测：含1200例测试集转换",
 mean=s[[paste0(m,"_mean")]],sd=s[[paste0(m,"_std")]])))
timing$phase <- factor(timing$phase,levels=c("训练：含标准化拟合与转换","预测：含1200例测试集转换"))
stopifnot(all(timing$mean-timing$sd>0))
t <- ggplot(timing,aes(model,mean,color=setting,shape=setting)) +
 geom_errorbar(aes(ymin=mean-sd,ymax=mean+sd),position=position_dodge(.45),width=.18,linewidth=.5) +
 geom_point(position=position_dodge(.45),size=2.6) + facet_wrap(~phase,ncol=1,scales="free_y") +
 scale_y_log10() + scale_color_manual(values=academic_palette("okabe-ito",8)[1:2],name="特征处理") +
 scale_shape_discrete(name="特征处理") + labs(x="分类器",y="耗时（秒，对数坐标）") +
 theme_academic(base_size=10,base_family=font) + theme(legend.position="bottom")
t <- add_figure_context(t,"图4-2 标准化前后的计算耗时","每设置预热1次后计时5次；数值库线程上限为1",
 "点为均值，误差条为±1样本标准差（ddof=1），不是置信区间。",base_size=10)
out <- file.path(args[1],"figures");dir.create(out,showWarnings=FALSE)
for (name in c("q4_quality","q4_timing")) {
 fig <- if(name=="q4_quality") q else t
 save_academic_plot(fig,file.path(out,paste0(name,".png")),178,145,300)
 ggsave(file.path(out,paste0(name,".pdf")),fig,device=cairo_pdf,width=178,height=145,units="mm",family=font)
}
writeLines(capture.output(sessionInfo()),file.path(out,"r_session.txt"))
