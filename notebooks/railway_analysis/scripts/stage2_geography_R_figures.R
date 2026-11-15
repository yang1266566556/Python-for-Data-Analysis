# Visualize user-verified geographic results; no model fitting.
args<-commandArgs(trailingOnly=TRUE);if(length(args)!=1L)stop("Expected config")
source(args[[1]],encoding="UTF-8")
suppressPackageStartupMessages(library(ggplot2));suppressPackageStartupMessages(library(patchwork))
source("C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R",encoding="UTF-8")
source(file.path(scripts,"stage2_plot_style.R"),encoding="UTF-8")
dir.create(output,recursive=TRUE,showWarnings=FALSE)
read_data<-function(n)read.csv(file.path(input,n),fileEncoding="UTF-8-BOM",check.names=FALSE,stringsAsFactors=FALSE)
nodes<-read_data("nodes_34_geographic_reference.csv");grid<-read_data("projected_graticule.csv")
aligned<-read_data("aligned_coordinates.csv");quality<-read_data("geographic_alignment_quality.csv");pairs<-read_data("time_geographic_city_pairs.csv");examples<-read_data("candidate_city_pair_examples.csv")
summary<-jsonlite::fromJSON(file.path(input,"geographic_summary.json"))
label_km<-function(d,x,y) {
  d$x<-d[[x]]/1000;d$y<-d[[y]]/1000;d<-place_labels(d)
  d$lx<-d$lx*1000;d$ly<-d$ly*1000;d
}
nodes$city<-nodes$representative_city;nodes$kind<-ifelse(nodes$node_id=="N34","台北：结构惩罚",ifelse(nodes$node_id=="N33","澳门：接驳假设","其他铁路节点"))
limits_x<-range(nodes$aeqd_x_km)+c(-500,500);limits_y<-range(nodes$aeqd_y_km)+c(-500,500)
viewed<-aligned[aligned$fit_scope=="all33" | (aligned$model=="MDS" & aligned$fit_scope=="all34") |
                  (aligned$model=="MDS" & aligned$fit_scope=="network33" & aligned$node_id!="N34"),]
overlay_limits_x<-range(nodes$aeqd_x_km,viewed$aligned_x_km)+c(-500,500)
overlay_limits_y<-range(nodes$aeqd_y_km,viewed$aligned_y_km)+c(-500,500)
geo_base<-function(xlim=limits_x,ylim=limits_y) ggplot()+geom_path(data=grid,aes(x_km,y_km,group=line_id),color="#E1E5E7",linewidth=.3)+
  coord_equal(xlim=xlim,ylim=ylim)+labs(x="方位等距投影X（公里）",y="方位等距投影Y（公里）")+base
labels<-label_km(nodes,"aeqd_x_km","aeqd_y_km")
p<-geo_base()+geom_segment(data=labels,aes(aeqd_x_km,aeqd_y_km,xend=lx,yend=ly),color="#999999",linewidth=.25)+
  geom_point(data=nodes,aes(aeqd_x_km,aeqd_y_km,color=kind),size=2.5)+
  geom_text(data=labels,aes(lx,ly,label=city),family=font,size=3)+scale_color_manual(values=colors,name=NULL)+
  labs(title="34个城市地理参考点",subtitle="球面方位等距投影；中心105°E、35°N；经纬网间隔10°",
       caption="Natural Earth城市点，固定数据提交2022-05-13；CRS84/WGS84经纬度，非车站或口岸测量坐标。\n仅示城市位置，不绘行政边界；澳门运营端点仍为关闸澳门侧。坐标单位公里，地理距离另用球面大圆公式。")
save_pair(p,"geography_city_reference34",10,8)

overlay<-function(d,title,subtitle) {
  labels<-label_km(d,"geo_x_km","geo_y_km")
  geo_base(overlay_limits_x,overlay_limits_y)+geom_segment(data=d,aes(geo_x_km,geo_y_km,xend=aligned_x_km,yend=aligned_y_km),color="#B6B6B6",linewidth=.35)+
    geom_point(data=d,aes(geo_x_km,geo_y_km,color="地理参考点"),size=1.9)+
    geom_point(data=d,aes(aligned_x_km,aligned_y_km,color="对齐后的嵌入"),shape=1,size=2.2,stroke=.5)+
    geom_segment(data=labels,aes(geo_x_km,geo_y_km,xend=lx,yend=ly),linewidth=.2,color="#ABABAB")+
    geom_text(data=labels,aes(lx,ly,label=city),size=2.8,family=font)+
    scale_color_manual(values=c("地理参考点"="#427C8A","对齐后的嵌入"="#C88639"),name=NULL)+
    labs(title=title,subtitle=subtitle)
}
plots<-lapply(c("MDS","MDS_nonmetric","tSNE","UMAP"),function(model) {
  d<-aligned[aligned$dataset_id=="access_60_n33" & aligned$model==model & aligned$fit_scope=="all33",]
  q<-quality[quality$dataset_id=="access_60_n33" & quality$model==model,]
  overlay(d,if(model=="MDS_nonmetric")"非度量MDS" else if(model=="tSNE")"t-SNE" else model,
          paste0("形状差异=",sprintf("%.3f",q$projected_procrustes_disparity),"；地理距离秩相关=",sprintf("%.3f",q$geo_distance_spearman)))
})
for(i in 2:4)plots[[i]]<-plots[[i]]+guides(color="none")
p<-wrap_plots(plots,ncol=2,guides="collect")+plot_annotation(title="连通33节点嵌入与地理位置的对照",
  caption="每个嵌入只做整体平移、旋转/反射和统一尺度拟合；实心点为地理参考，空心点为变换后的嵌入。\n灰线表示同一城市的投影形状差异，不是交通路线或旅行误差；地理相似性不能替代铁路时间保持指标。")
p<-p & theme(legend.position="bottom",plot.title=element_text(family=font,size=13,face="bold"),plot.subtitle=element_text(family=font,size=9),plot.caption=element_text(family=font,size=9,hjust=0))
save_pair(p,"geography_connected33_model_alignment",16,12)

mds_list<-list(aligned[aligned$dataset_id=="access_60_alpha_5_n34" & aligned$model=="MDS" & aligned$fit_scope=="all34",],
               aligned[aligned$dataset_id=="access_60_alpha_5_n34" & aligned$model=="MDS" & aligned$fit_scope=="network33" & aligned$node_id!="N34",],
               aligned[aligned$dataset_id=="access_60_n33" & aligned$model=="MDS" & aligned$fit_scope=="all33",])
titles<-c("完整34点拟合并评分","34节点结果：仅用连通33点对齐","单独33节点结果对齐")
plots<-lapply(1:3,function(i)overlay(mds_list[[i]],titles[i],"度量MDS；seed42；澳门接驳60分钟"))
for(i in 2:3)plots[[i]]<-plots[[i]]+guides(color="none")
p<-wrap_plots(plots,nrow=1,guides="collect")+plot_annotation(title="台北惩罚对MDS地理形状对照的影响",
  caption="三个面板均为同一地理投影和坐标范围；中图未重新训练MDS，也未显示未参与对齐的台北外推点。\n相似变换残差只描述几何偏差，不能解释为铁路通行误差。")
p<-p & theme(legend.position="bottom",plot.title=element_text(family=font,size=12,face="bold"),plot.subtitle=element_text(family=font,size=9),plot.caption=element_text(family=font,size=9,hjust=0))
save_pair(p,"geography_MDS_penalty_alignment",18,7)

quality$scope<-factor(paste(quality$dataset_id,quality$fit_scope),levels=c("access_60_alpha_5_n34 all34","access_60_alpha_5_n34 network33","access_60_n33 all33"),
                     labels=c("34拟合：全部34点对齐","34拟合：连通33点对齐","33拟合：全部33点对齐"))
quality$model<-factor(quality$model,levels=c("MDS","MDS_nonmetric","tSNE","UMAP"),labels=c("MDS","非度量MDS","t-SNE","UMAP"))
long<-rbind(transform(quality,metric="投影Procrustes差异 ↓",value=projected_procrustes_disparity),transform(quality,metric="球面地理距离秩相关 ↑",value=geo_distance_spearman))
p<-ggplot(long,aes(model,value,color=scope,shape=scope))+geom_point(position=position_dodge(.38),size=2.8)+facet_wrap(~metric,scales="free_y")+
  scale_color_manual(values=c("#427C8A","#C88639","#916380"),name=NULL)+scale_shape_discrete(name=NULL)+
  labs(title="地理相似性与对齐范围的定量比较",subtitle="固定代表参数及seed42；相同城市点参考",x="降维模型",y="指标值（无量纲）",
       caption="这是嵌入与地理参考的描述性比较，不是原铁路时间上的算法质量排名。\n全34点与连通33点评分范围不同；投影残差与球面地理距离秩相关是不同指标。")+base
save_pair(p,"geography_alignment_quality",11,5.5)

pairs$kind<-ifelse(pairs$includes_assumed_Macao_access,"含澳门接驳假设","其他连通城市对")
marked<-do.call(rbind,lapply(unique(examples$example_group),function(g)head(examples[examples$example_group==g,],3)))
marked$city<-paste(marked$city_a,marked$city_b,sep="—");marked$x<-marked$geographic_great_circle_km/1000;marked$y<-marked$symmetric_time_min/1000;marked<-place_labels(marked)
p<-ggplot(pairs,aes(geographic_great_circle_km,symmetric_time_min))+geom_point(aes(color=kind),alpha=.55,size=1.7)+
  geom_segment(data=marked,aes(geographic_great_circle_km,symmetric_time_min,xend=lx*1000,yend=ly*1000),color="#777777",linewidth=.3)+
  geom_text(data=marked,aes(lx*1000,ly*1000,label=city),family=font,size=3)+
  scale_color_manual(values=c("含澳门接驳假设"="#C88639","其他连通城市对"="#427C8A"),name=NULL)+
  labs(title="铁路时间成本与球面地理距离",subtitle=paste0("连通33节点的528个无向城市对；Spearman rho=",sprintf("%.4f",summary$time_geography_spearman_33)),
       x="城市参考点大圆距离（公里）",y="双向平均候选通行时间（分钟）",
       caption="不含台北算法惩罚；澳门含60分钟接驳假设，地理参考不是铁路站点坐标。\n城市对并非独立抽样，相关系数只作描述；图中线段仅连接标签，不是回归或交通线路。")+base
save_pair(p,"geography_time_distance_pairs",10,7)

shown<-do.call(rbind,lapply(unique(examples$example_group),function(g)head(examples[examples$example_group==g,],5)))
shown$pair<-paste(shown$city_a,shown$city_b,sep="—");shown$pair<-factor(shown$pair,levels=shown$pair[order(shown$time_minus_geographic_rank)])
p<-ggplot(shown,aes(time_minus_geographic_rank,pair))+geom_vline(xintercept=0,color="#999999",linewidth=.3)+
  geom_segment(aes(x=0,xend=time_minus_geographic_rank,yend=pair),color="#BDC5C8",linewidth=1)+
  geom_point(aes(color=time_minus_geographic_rank>0),size=3)+scale_color_manual(values=c("TRUE"="#B47B44","FALSE"="#427C8A"),guide="none")+
  labs(title="相对于地理距离的时间成本排名差异示例",subtitle="预设：大圆距离至少200公里；两类各取5对",x="时间秩分位 − 地理距离秩分位（无量纲）",y="城市对",
       caption="正值表示相对时间成本排名偏高，负值表示相对偏低；依据本研究的日期、站点与换乘规则。\n示例是解释线索，不证明经济因果、运行速度或线路建设收益。")+base
save_pair(p,"geography_city_pair_rank_examples",10,6.5)
writeLines(c(R.version.string,"Used verified user geographical output only; no scientific fitting in R.",
 "Projection is spherical AEQD centered 105E/35N, kilometre coordinates; intercity distances use haversine.",
 "Natural Earth city-reference points only, not operational station positions; no administrative boundaries drawn.",
 "r-academic-plots theme and shared style; private book originals unavailable; all figures titled."),file.path(output,"R_figure_provenance.txt"),useBytes=TRUE)
cat("GEOGRAPHY_R_FIGURES_COMPLETED\n")
