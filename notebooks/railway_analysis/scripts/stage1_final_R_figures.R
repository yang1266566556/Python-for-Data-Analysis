# Assistant-run scientific figures using r-academic-plots; no installations.
args <- commandArgs(trailingOnly=TRUE)
if(length(args)==1L) {
  source(args[[1]],encoding="UTF-8")
} else if(length(args)==2L) {
  input <- args[[1]]; output <- args[[2]]
} else stop("Expected config R file, or verified matrix directory and output directory")
if(!requireNamespace("ggplot2",quietly=TRUE)) stop("Existing ggplot2 library could not be loaded")
suppressPackageStartupMessages(library(ggplot2))
source("C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R",encoding="UTF-8")
dir.create(output,recursive=TRUE,showWarnings=FALSE)
read_data <- function(name) read.csv(file.path(input,name),fileEncoding="UTF-8-BOM",check.names=FALSE,stringsAsFactors=FALSE)
nodes <- read_data("nodes_34.csv")
raw <- read_data("raw34_access_60.csv")
catalog <- read_data("matrix_input_catalog.csv")
main <- catalog[catalog$access_assumption_min==60 & catalog$penalty_alpha==5,]
algorithm <- read_data(main$symmetric_csv)
ids <- nodes$node_id; cities <- nodes$representative_city
make_long <- function(frame) {
  values <- as.matrix(frame[,-1]); storage.mode(values) <- "double"
  data.frame(from=rep(cities,each=length(ids)),to=rep(cities,times=length(ids)),
             value=as.vector(t(values)),stringsAsFactors=FALSE)
}
raw_long <- make_long(raw); algorithm_long <- make_long(algorithm)
font <- "Microsoft YaHei"
base <- theme_academic(base_size=10,base_family=font) +
  theme(plot.title=element_text(size=15,face="bold",margin=margin(b=8)),
        plot.subtitle=element_text(size=10,margin=margin(b=10)),
        plot.caption=element_text(size=9,hjust=0,color="#505050",margin=margin(t=10)),
        plot.margin=margin(14,16,14,14),legend.title=element_text(size=10),legend.text=element_text(size=9))
save_pair <- function(p,name,w,h) {
  # User explicitly requires a title on every figure. This overrides the
  # skill's title-free clean-version default; final assets all retain titles.
  ggsave(file.path(output,paste0(name,".png")),p,width=w,height=h,units="in",dpi=300,bg="white",device=grDevices::png,type="cairo")
  ggsave(file.path(output,paste0(name,".pdf")),p,width=w,height=h,units="in",device=grDevices::cairo_pdf,bg="white")
}
heat <- function(data,palette,title,subtitle,caption,raw_mode=FALSE) {
  data$from <- factor(data$from,levels=rev(cities));data$to <- factor(data$to,levels=cities)
  data$display_value <- ifelse(is.finite(data$value),data$value,NA_real_)
  p <- ggplot(data,aes(x=to,y=from)) +
    geom_tile(aes(fill=display_value),color="white",linewidth=0.12) +
    scale_fill_gradientn(colors=academic_palette(palette,128),na.value="#DFE3E6",
                         name=if(raw_mode) "模型历时\n（分钟）" else "算法差异值\n（分钟标度）") +
    scale_x_discrete(expand=c(0,0)) + scale_y_discrete(expand=c(0,0)) + coord_fixed() +
    labs(title=title,subtitle=subtitle,x="到达代表城市",y="出发代表城市",caption=caption) + base +
    theme(axis.text.x=element_text(angle=90,vjust=.5,hjust=1,size=8),axis.text.y=element_text(size=8),
          axis.line=element_blank(),axis.ticks=element_blank())
  if(raw_mode) p <- p + geom_point(data=data[!is.finite(data$value),],shape=4,size=1.3,stroke=.3,color="#4A4A4A")
  p
}
for(palette in c("bluegreen","cassatt","hiroshige")) {
  p <- heat(raw_long,palette,"34节点原始有向通行时间", "澳门接驳假设60分钟；台北铁路结构不可达单独标记",
            "单位：分钟；灰色叉号为台北66个结构不可达单元格，不表示普通数据缺失。\n首程2026-11-18；来源为已核验12306时刻表及明确的澳门接驳假设。",TRUE)
  name <- if(palette=="bluegreen") "fig1_raw_directed34_final" else paste0("palette_candidate_",palette)
  save_pair(p,name,11,10)
}
p_alg <- heat(algorithm_long,"bluegreen","34节点算法输入：双向平均与台北惩罚", "澳门接驳60分钟；台北惩罚 α = 5，P = 22,775",
              "颜色是算法差异值；台北惩罚不是实际通行时间。原始有向数据另存，算法副本采用 (Tij + Tji) / 2。")
save_pair(p_alg,"fig2_algorithm34_main",11,10)
finite <- raw_long[is.finite(raw_long$value) & raw_long$from!=raw_long$to,]
median_time <- median(finite$value)
p_dist <- ggplot(finite,aes(x=value)) +
  geom_histogram(binwidth=120,boundary=0,fill="#378D87",color="white",linewidth=.25) +
  geom_vline(xintercept=median_time,linetype="dashed",linewidth=.5,color="#333333") +
  scale_x_continuous(breaks=seq(0,5040,720),expand=expansion(mult=c(0,.02))) +
  labs(title="33节点有限通行时间的分布",subtitle=paste0("1056个有向城市对；中位数 ",format(median_time,trim=TRUE)," 分钟（虚线）"),
       x="已采时刻表模型的候选历时（分钟）",y="有向城市对数量（对）",
       caption="不含对角线和台北不可达惩罚；澳门含60分钟接驳假设。\n这是规定站点、日期和换乘条件内的结果，不是全国完整时刻表的全局最短证明。") + base
save_pair(p_dist,"fig3_finite_time_distribution",8.5,5.5)
shares <- catalog[catalog$access_assumption_min==60,]
shares$alpha <- factor(shares$penalty_alpha,levels=c(2,5,10),labels=c("2 × Tref","5 × Tref","10 × Tref"))
p_share <- ggplot(shares,aes(x=alpha,y=penalty_share_of_pairwise_sum)) +
  geom_col(width=.56,fill="#5676A1") +
  geom_text(aes(label=sprintf("%.1f%%",penalty_share_of_pairwise_sum*100)),vjust=-.4,family=font,size=4) +
  scale_y_continuous(limits=c(0,1),breaks=seq(0,1,.2),labels=function(x)paste0(round(x*100),"%"),expand=expansion(mult=c(0,.02))) +
  labs(title="台北惩罚量级对差异值总和的影响",subtitle="澳门接驳60分钟；Tref = 4555分钟，有限时间部分保持一致",
       x="台北惩罚参数",y="惩罚项占算法差异值总和的比例",
       caption="66个惩罚单元格仅占1122个有向非对角单元格的5.9%。\n比例描述矩阵数值权重，不是客流、实际旅行时间或经济联系份额。") + base
save_pair(p_share,"fig4_penalty_weight_sensitivity",8.5,5.5)
writeLines(c(R.version.string,paste("ggplot2",as.character(packageVersion("ggplot2"))),
             paste("font",font),"Used installed skill academic_plot_helpers.R; original private source roots absent.",
             "All figures titled per user requirement; no title-free clean export.",
             paste("finite_directed_count",nrow(finite)),paste("median_finite_minutes",median_time)),
           file.path(output,"R_figure_provenance.txt"),useBytes=TRUE)
cat("FINAL_R_FIGURES_COMPLETED\n")
