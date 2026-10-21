# 助手使用已核验的五折结果作图，不运行分类模型。
args <- commandArgs(trailingOnly=TRUE)
library(ggplot2)
library(patchwork)
source("C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R",encoding="UTF-8")
s <- read.csv(file.path(args[1],"q5_summary.csv"),stringsAsFactors=FALSE)
stopifnot(nrow(s)==47,all(tolower(as.character(s$eligible))=="true"))
font <- "Microsoft YaHei"
colors <- c("折内训练macro-F1"="#777777","验证macro-F1"="#0072B2","验证Accuracy"="#E69F00")
metrics <- c("train_macro_f1","validation_macro_f1","validation_accuracy")
curve_labels <- names(colors)
make_panel <- function(id,param) {
  d <- s[s$scan_id==id,];d <- d[order(d$candidate_index),]
  if(param=="max_depth") {
    x <- d$candidate_index
    labels <- ifelse(d$value_label=="None","不限制",d$value_label)
  } else {
    x <- as.numeric(d$value_label)
    labels <- ifelse(abs(x-1/24)<1e-12 & param=="gamma","1/24",sprintf("%.4g",x))
    labels <- trimws(labels)
  }
  long <- do.call(rbind,lapply(seq_along(metrics),function(i) data.frame(
    x=x,curve=curve_labels[i],mean=d[[paste0(metrics[i],"_mean")]],sd=d[[paste0(metrics[i],"_std")]])))
  long$curve <- factor(long$curve,levels=curve_labels)
  selected_x <- x[which.max(d$validation_macro_f1_mean)]
  p <- ggplot(long,aes(x,mean,color=curve,fill=curve,linetype=curve)) +
    geom_ribbon(aes(ymin=mean-sd,ymax=mean+sd),alpha=.10,color=NA,show.legend=FALSE) +
    geom_line(linewidth=.55) + geom_point(size=1.7) +
    geom_vline(xintercept=selected_x,linetype="dotted",color="#666666",linewidth=.45) +
    scale_color_manual(values=colors,name=NULL) + scale_fill_manual(values=colors,name=NULL) +
    scale_linetype_manual(values=c("dashed","solid","solid"),name=NULL) +
    coord_cartesian(ylim=c(0,1)) + scale_y_continuous(breaks=seq(0,1,.25)) +
    labs(x=param,y="五折指标均值") + theme_academic(base_size=9,base_family=font) +
    theme(legend.position="bottom")
  if(param %in% c("C","gamma","n_neighbors","min_samples_leaf")) {
    p <- p + scale_x_log10(breaks=x,labels=labels) + labs(x=paste0(param,"（对数坐标）"))
  } else {
    p <- p + scale_x_continuous(breaks=x,labels=labels)
    if(param=="max_depth") p <- p + labs(x="max_depth（按候选顺序排列）")
  }
  p
}
specs <- list(
 list("lr","逻辑回归",c("lr_C","lr_l1_ratio"),c("C","l1_ratio")),
 list("tree","决策树",c("tree_max_depth","tree_min_samples_leaf"),c("max_depth","min_samples_leaf")),
 list("knn","KNN",c("knn_n_neighbors","knn_p"),c("n_neighbors","p")),
 list("svc","SVC",c("svc_C","svc_gamma"),c("C","gamma")))
out <- file.path(args[1],"figures");dir.create(out,showWarnings=FALSE)
for(i in seq_along(specs)) {
  sp <- specs[[i]]
  fig <- (make_panel(sp[[3]][1],sp[[4]][1]) / make_panel(sp[[3]][2],sp[[4]][2])) +
    plot_layout(guides="collect") +
    plot_annotation(title=paste0("图5-",i," ",sp[[2]],"的参数影响"),
      subtitle="每次仅改变一个参数；使用训练集内部相同五折；测试集未参与选参",
      caption="阴影为±1样本标准差（ddof=1），不是置信区间。\n竖虚线标出各扫描的推荐值；两个推荐值不能直接合并为联合最优。",
      theme=theme(text=element_text(family=font),plot.title=element_text(size=13,face="bold"),
                  plot.subtitle=element_text(size=9),plot.caption=element_text(size=8,hjust=0))) &
    theme(legend.position="bottom",text=element_text(family=font))
  save_academic_plot(fig,file.path(out,paste0("q5_",sp[[1]],".png")),178,165,300)
  ggsave(file.path(out,paste0("q5_",sp[[1]],".pdf")),fig,device=cairo_pdf,width=178,height=165,units="mm",family=font)
}
writeLines(capture.output(sessionInfo()),file.path(out,"r_session.txt"))
