# R-only visualization of authenticated user-run coordinates; no model fits.
args <- commandArgs(trailingOnly=TRUE)
if(length(args)!=1L) stop("Expected UTF-8 config file")
source(args[[1]],encoding="UTF-8")
suppressPackageStartupMessages(library(ggplot2))
suppressPackageStartupMessages(library(patchwork))
source("C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R",encoding="UTF-8")
dir.create(output,recursive=TRUE,showWarnings=FALSE)
read_data <- function(n) read.csv(file.path(input,n),fileEncoding="UTF-8-BOM",check.names=FALSE,stringsAsFactors=FALSE)
coords <- read_data("coordinates_all.csv"); metrics <- read_data("baseline_metrics.csv")
font <- "Microsoft YaHei"
base <- theme_academic(base_size=10,base_family=font) +
  theme(plot.title=element_text(size=12,face="bold",margin=margin(b=7)),
        plot.subtitle=element_text(size=9,margin=margin(b=9)),
        plot.caption=element_text(size=9,hjust=0,color="#505050",margin=margin(t=10)),
        plot.margin=margin(12,13,12,12),legend.position="bottom")
save_pair <- function(p,name,w,h) {
  # User requires all figures to have titles, overriding title-free clean default.
  ggsave(file.path(output,paste0(name,".png")),p,width=w,height=h,units="in",dpi=300,bg="white",device=grDevices::png,type="cairo")
  ggsave(file.path(output,paste0(name,".pdf")),p,width=w,height=h,units="in",device=grDevices::cairo_pdf,bg="white")
}
normalize_display <- function(d) {
  d$x <- d$embedding_1-mean(d$embedding_1);d$y <- d$embedding_2-mean(d$embedding_2)
  scale <- sqrt(mean(d$x^2+d$y^2));d$x<-d$x/scale;d$y<-d$y/scale
  d$kind<-ifelse(d$node_id=="N34","台北：结构惩罚",ifelse(d$node_id=="N33","澳门：接驳假设","其他铁路节点"))
  d
}
# Lightweight deterministic label placement, avoiding a new package install.
place_labels <- function(d) {
  d$lx<-d$x;d$ly<-d$y
  widths <- pmax(.26,nchar(d$city)*.17);height<-.27
  offsets<-expand.grid(dx=seq(-1.8,1.8,.15),dy=seq(-1.8,1.8,.15))
  offsets<-offsets[order(offsets$dx^2+offsets$dy^2),]
  placed<-integer()
  for(i in order(-nchar(d$city),d$x,d$y)) {
    for(j in seq_len(nrow(offsets))) {
      x<-d$x[i]+offsets$dx[j];y<-d$y[i]+offsets$dy[j]+.08
      collision<-any(abs(x-d$lx[placed])<(widths[i]+widths[placed])/2 & abs(y-d$ly[placed])<height)
      covers_point<-any(abs(x-d$x)<widths[i]/2 & abs(y-d$y)<.08)
      if(!collision && !covers_point) {d$lx[i]<-x;d$ly[i]<-y;break}
    }
    placed<-c(placed,i)
  }
  d
}
colors<-c("其他铁路节点"="#427C8A","澳门：接驳假设"="#C88639","台北：结构惩罚"="#B4535B")
panel <- function(d,title,subtitle,label_all=TRUE) {
  d<-normalize_display(d)
  labels<-if(label_all) place_labels(d) else place_labels(d[d$node_id%in%c("N33","N34","N26","N21"),])
  ggplot(d,aes(x,y))+
    geom_hline(yintercept=0,linewidth=.2,color="#E5E7E9")+geom_vline(xintercept=0,linewidth=.2,color="#E5E7E9")+
    geom_segment(data=labels,aes(x=x,y=y,xend=lx,yend=ly),inherit.aes=FALSE,color="#969696",linewidth=.25)+
    geom_point(aes(color=kind),size=2.3)+
    geom_text(data=labels,aes(x=lx,y=ly,label=city),inherit.aes=FALSE,family=font,size=3,color="black")+
    scale_color_manual(values=colors,limits=if(any(d$node_id=="N34"))names(colors) else names(colors)[1:2],drop=FALSE,name=NULL)+
    scale_x_continuous(expand=expansion(mult=.16))+scale_y_continuous(expand=expansion(mult=.16))+
    coord_equal(clip="off")+labs(title=title,subtitle=subtitle,x="嵌入维度1（无地理单位）",y="嵌入维度2（无地理单位）")+base
}
for(alg in c("MDS","tSNE","UMAP")) {
  full<-coords[coords$algorithm==alg & coords$dataset_id=="access_60_alpha_5_n34",]
  control<-coords[coords$algorithm==alg & coords$dataset_id=="access_60_n33",]
  left<-panel(full,"A  完整34节点","台北惩罚P=22775；仅标关键节点",FALSE)
  middle<-panel(full[full$node_id!="N34",],"B  同一拟合中的连通33点","仅取出并放大坐标，未重新拟合")+guides(color="none")
  right<-panel(control,"C  单独拟合33节点对照","输入不含台北；含澳门接驳假设")+guides(color="none")
  title<-if(alg=="MDS") "MDS基线：惩罚节点与连通网络对照" else if(alg=="tSNE") "t-SNE基线：完整网络与连通网络对照" else "UMAP基线：完整网络与连通网络对照"
  parameter<-if(alg=="MDS") "度量MDS；n_init=4；max_iter=1000" else if(alg=="tSNE") "perplexity=10；max_iter=1000；exact" else "n_neighbors=10；min_dist=0.1；n_epochs=500"
  p<-(left+middle+right)+plot_layout(guides="collect",widths=c(1,1,1))+
    plot_annotation(title=title,subtitle=paste0(parameter,"；seed=42；澳门接驳假设60分钟"),
      caption="每个面板仅为显示而居中、统一缩放；面板坐标尺度不能直接互比，也不代表经纬度或分钟。\n全部城市名称见B/C及A中台北标签；颜色只区分节点处理方式，不是聚类结果。",
      theme=theme(plot.title=element_text(family=font,size=16,face="bold"),plot.subtitle=element_text(family=font,size=10),
        plot.caption=element_text(family=font,size=9,hjust=0),plot.margin=margin(14,14,14,14)))
  p<-p & theme(legend.position="bottom",plot.title=element_text(family=font,size=13,face="bold"),
               plot.subtitle=element_text(family=font,size=9),plot.caption=element_text(family=font,size=9,hjust=0))
  save_pair(p,paste0("baseline_",alg,"_network_comparison"),18,7)
  standalone<-panel(control,paste0(if(alg=="tSNE")"t-SNE" else alg,"基线：连通33节点"),paste0(parameter,"；seed=42"))+
    labs(caption="城市标签通过引线避让；点的位置来自用户保存的实际坐标。\n坐标仅作显示归一化，不是经纬度或分钟；澳门含60分钟接驳假设，颜色不是聚类。")
  save_pair(standalone,paste0("baseline_",alg,"_connected33"),8,7.5)
}
# Same metric definitions across algorithms; native stress and KL never mixed.
metric_names<-c(external_scale_fitted_stress1="外部尺度拟合stress（越小越好）",distance_spearman="距离秩相关（越大越好）",
                neighbor_overlap_k5="5近邻重叠率（越大越好）",trustworthiness_k5="5近邻可信度（越大越好）")
long<-do.call(rbind,lapply(names(metric_names),function(k)do.call(rbind,lapply(seq_len(nrow(metrics)),function(i) {
  row<-metrics[i,];full<-row$node_count==34
  rbind(data.frame(algorithm=row$algorithm,metric=metric_names[k],value=row[[k]],scope=if(full)"34拟合：全部节点" else "33拟合：全部节点"),
        if(full)data.frame(algorithm=row$algorithm,metric=metric_names[k],value=row[[paste0("network_only_",k)]],scope="34拟合：只评估连通33点") else NULL)
}))))
long$algorithm<-factor(long$algorithm,levels=c("MDS","tSNE","UMAP"))
long$metric<-factor(long$metric,levels=unname(metric_names))
p<-ggplot(long,aes(algorithm,value,color=scope,shape=scope))+
  geom_point(position=position_dodge(width=.38),size=2.8)+
  facet_wrap(~metric,ncol=2,scales="free_y")+
  scale_color_manual(values=c("34拟合：全部节点"="#427C8A","34拟合：只评估连通33点"="#C88639","33拟合：全部节点"="#916380"),name=NULL)+
  scale_shape_manual(values=c("34拟合：全部节点"=16,"34拟合：只评估连通33点"=17,"33拟合：全部节点"=15),name=NULL)+
  labs(title="三算法基线的统一外部质量指标",subtitle="同一距离定义；seed=42；比较完整节点指标与连通网络内部指标",x="降维算法",y="指标值（无量纲）",
       caption="参考为冻结的对称时间差异矩阵；所有算法输入统一除以537.5。\n34节点总stress受大惩罚量级影响，需结合连通33点指标解释；这里只是单种子基线，尚非最终算法优劣结论。")+base+
  theme(legend.position="bottom",legend.text=element_text(size=9),strip.text=element_text(size=10))
save_pair(p,"baseline_external_quality",10.5,7)
writeLines(c(R.version.string,paste("ggplot2",packageVersion("ggplot2")),paste("patchwork",packageVersion("patchwork")),
  "Used r-academic-plots helper; private book sources unavailable. All figures titled per user request.",
  "No new model fitting: authenticated user coordinates only. Per-panel isotropic display normalization, original CSV unchanged.",
  "Labels placed with deterministic R function; no extra package installed."),file.path(output,"R_figure_provenance.txt"),useBytes=TRUE)
cat("BASELINE_R_FIGURES_COMPLETED\n")
