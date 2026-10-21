args <- commandArgs(trailingOnly=TRUE)
library(ggplot2)
source('C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R',encoding='UTF-8')
root <- args[1]; out <- file.path(root,'figures');dir.create(out,showWarnings=FALSE)
cv <- read.csv(file.path(root,'q7_cv_summary.csv'))
test <- read.csv(file.path(root,'q7_test_summary.csv'))
pc <- read.csv(file.path(root,'q7_per_class.csv'))
font <- 'Microsoft YaHei'
colors <- setNames(academic_palette('okabe-ito',2),c('none','balanced'))
common <- function(p,title,subtitle,caption) {
  p + scale_color_manual(values=colors,labels=c('原始权重','balanced'),name='类别权重') +
    theme_academic(base_size=10,base_family=font) +
    labs(title=title,subtitle=subtitle,caption=caption) +
    theme(legend.position='bottom',plot.title=element_text(size=13,face='bold'),
      plot.subtitle=element_text(size=9),plot.caption=element_text(size=8,hjust=0))
}
savefig <- function(p,name,h) {
  save_academic_plot(p,file.path(out,paste0(name,'.png')),178,h,300)
  ggsave(file.path(out,paste0(name,'.pdf')),p,device=cairo_pdf,width=178,height=h,units='mm',family=font)
}
overall <- do.call(rbind,lapply(c('accuracy','macro_f1'),function(metric) rbind(
  data.frame(strategy=cv$strategy,subset='训练集内部五折验证',metric=metric,
    value=cv[[paste0(metric,'_mean')]],sd=cv[[paste0(metric,'_std')]]),
  data.frame(strategy=test$strategy,subset='固定测试集',metric=metric,value=test[[metric]],sd=NA))))
overall$strategy <- factor(overall$strategy,levels=c('none','balanced'))
overall$metric <- factor(overall$metric,levels=c('accuracy','macro_f1'),labels=c('Accuracy','macro-F1'))
overall$subset <- factor(overall$subset,levels=c('训练集内部五折验证','固定测试集'))
pos <- position_dodge(width=.65)
p <- ggplot(overall,aes(metric,value,color=strategy,group=strategy)) +
  geom_errorbar(aes(ymin=value-sd,ymax=value+sd),position=pos,width=.10,na.rm=TRUE) +
  geom_point(position=pos,size=2.6) +
  geom_text(aes(label=sprintf('%.4f',value)),position=pos,vjust=-1.3,size=2.8,family=font,show.legend=FALSE) +
  facet_wrap(~subset,nrow=1) + scale_y_continuous(limits=c(0,1),breaks=seq(0,1,.2)) +
  labs(x='评价指标',y='得分')
p <- common(p,'图7-1 类别权重对总体指标的影响','相同标准化SVC，仅改变class_weight；C=1，gamma=scale',
  '验证误差线为五折±1样本标准差，不是置信区间；测试集只展示本次固定划分。')
savefig(p,'q7_overall',122)
long <- rbind(data.frame(pc,metric='Recall',value=pc$recall),data.frame(pc,metric='F1',value=pc$f1))
long$strategy <- factor(long$strategy,levels=c('none','balanced'))
long$metric <- factor(long$metric,levels=c('Recall','F1'))
p <- ggplot(long,aes(class_label,value,color=strategy,group=strategy)) +
  annotate('rect',xmin=4.5,xmax=9.5,ymin=-Inf,ymax=Inf,fill='#F4F1E9',alpha=.8) +
  geom_line(linewidth=.55) + geom_point(size=2) + facet_wrap(~metric,ncol=1) +
  scale_x_continuous(breaks=0:9) + scale_y_continuous(limits=c(0,1),breaks=seq(0,1,.25)) +
  labs(x='类别标签（浅色背景为训练样本最少的五类）',y='测试集逐类得分')
p <- common(p,'图7-2 类别权重对逐类召回率与F1的影响','少数五类的召回率均提高；类别6的F1略降',
  '少数类组仅由训练集计数预先定义；逐类F1使用完整测试集计算，包含组外误报。')
savefig(p,'q7_per_class',164)
writeLines(capture.output(sessionInfo()),file.path(out,'r_session.txt'))
