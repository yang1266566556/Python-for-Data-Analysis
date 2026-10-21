# 仅从已核验的真实结果绘图；区域判断依据复用的训练内部验证。
args <- commandArgs(trailingOnly=TRUE)
library(ggplot2)
source('C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R',encoding='UTF-8')
root <- args[1]; out <- file.path(root,'figures');dir.create(out,showWarnings=FALSE)
s <- read.csv(file.path(root,'q8_scores.csv'))
s$selected_by_cv <- tolower(as.character(s$selected_by_cv)) == 'true'
cv <- read.csv(file.path(root,'q8_reused_cv_summary.csv'))
font <- 'Microsoft YaHei'
stopifnot(nrow(s)==7,nrow(cv)==7,sum(s$selected_by_cv)==1)
selected <- s$gamma[s$selected_by_cv]
palette <- academic_palette('okabe-ito',3)
make_plot <- function(d,title,subtitle,caption,colors) {
  p <- ggplot(d,aes(gamma,value,color=curve,group=curve)) +
    annotate('rect',xmin=.001,xmax=.01,ymin=0,ymax=1,fill='#E69F00',alpha=.08) +
    annotate('rect',xmin=.5,xmax=1,ymin=0,ymax=1,fill='#D55E00',alpha=.08) +
    geom_vline(xintercept=selected,linetype='dotted',color='#009E73',linewidth=.6) +
    geom_errorbar(aes(ymin=pmax(0,value-sd),ymax=pmin(1,value+sd)),width=.035,linewidth=.45,na.rm=TRUE) +
    geom_line(linewidth=.65) + geom_point(size=2.2) +
    annotate('text',x=.0032,y=1.07,label='低gamma采样点\n欠拟合',family=font,size=3,color='#855B00') +
    annotate('text',x=selected,y=1.07,label='验证推荐\n相对合适点',family=font,size=3,color='#007753') +
    annotate('text',x=.70,y=1.07,label='大gamma采样点\n明显过拟合',family=font,size=3,color='#A13F00') +
    scale_x_log10(breaks=s$gamma,labels=c('0.001','0.005','0.01','1/24','0.1','0.5','1')) +
    scale_y_continuous(breaks=seq(0,1,.2)) + coord_cartesian(ylim=c(0,1.13)) +
    scale_color_manual(values=colors,name='数据子集') +
    labs(title=title,subtitle=subtitle,x='gamma（对数坐标；C=1，class_weight=None）',y='macro-F1',caption=caption) +
    theme_academic(base_size=10,base_family=font) +
    theme(legend.position='bottom',plot.title=element_text(size=13,face='bold'),
      plot.subtitle=element_text(size=9),plot.caption=element_text(size=8,hjust=0))
  p
}
savefig <- function(p,name) {
  save_academic_plot(p,file.path(out,paste0(name,'.png')),178,142,300)
  ggsave(file.path(out,paste0(name,'.pdf')),p,device=cairo_pdf,width=178,height=142,units='mm',family=font)
}
d <- rbind(data.frame(gamma=s$gamma,value=s$train_macro_f1,sd=NA,curve='完整训练集（3600例）'),
           data.frame(gamma=s$gamma,value=s$test_macro_f1,sd=NA,curve='固定测试集（1200例）'))
d$curve <- factor(d$curve,levels=c('完整训练集（3600例）','固定测试集（1200例）'))
p <- make_plot(d,'图8-1 gamma对训练与测试macro-F1的影响',
  '标准化RBF-SVC；推荐值在本题测试评价前由第五题验证结果锁定',
  '拟合状态依据训练内部验证；着色仅概括已测采样点，不表示区间内每个值均已验证。\n1/24为当前候选中相对合适点；0.1泛化差距增大，未据测试曲线重新选参。',
  setNames(c('#777777',palette[1]),levels(d$curve)))
savefig(p,'q8_train_test')
d <- rbind(data.frame(gamma=as.numeric(cv$value_label),value=cv$train_macro_f1_mean,
    sd=cv$train_macro_f1_std,curve='折内训练（每折2880例）'),
  data.frame(gamma=as.numeric(cv$value_label),value=cv$validation_macro_f1_mean,
    sd=cv$validation_macro_f1_std,curve='折内验证（每折720例）'))
d$curve <- factor(d$curve,levels=c('折内训练（每折2880例）','折内验证（每折720例）'))
p <- make_plot(d,'图8-2 训练集内部验证与拟合程度',
  '复用第五题相同五折；gamma=1/24在五个验证折中均获推荐',
  '误差线为五折±1样本标准差，不是置信区间；折内训练均值不同于完整训练集分数。\n着色只概括已测点；无法确定连续的欠拟合/过拟合分界或最优参数区间。',
  setNames(c('#777777',palette[3]),levels(d$curve)))
savefig(p,'q8_validation')
writeLines(capture.output(sessionInfo()),file.path(out,'r_session.txt'))
