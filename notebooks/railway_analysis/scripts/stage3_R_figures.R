# Only visualize authenticated user cluster labels and scores.
args<-commandArgs(trailingOnly=TRUE);if(length(args)!=1L)stop("Expected config")
source(args[[1]],encoding="UTF-8")
suppressPackageStartupMessages(library(ggplot2));suppressPackageStartupMessages(library(patchwork))
source("C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R",encoding="UTF-8")
source(file.path(scripts,"stage2_plot_style.R"),encoding="UTF-8")
dir.create(output,recursive=TRUE,showWarnings=FALSE)
read_data<-function(n) {
  d<-read.csv(file.path(input,n),fileEncoding="UTF-8-BOM",check.names=FALSE,stringsAsFactors=FALSE)
  for(k in names(d)) if(is.character(d[[k]]) && any(!is.na(d[[k]])) && all(is.na(d[[k]])|d[[k]]%in%c("True","False"))) {
    value<-d[[k]];d[[k]]<-ifelse(is.na(value),NA,value=="True")
  }
  d
}
m<-read_data("cluster_metrics.csv");q<-read_data("representative_cluster_quality.csv");a<-read_data("assignments_for_plot.csv")
grid<-read_data("projected_graticule.csv");nodes<-read_data("nodes_34_geographic_reference.csv");reps<-read_data("representation_inventory.csv")
comparison<-read_data("comparison_for_plot.csv");stable<-read_data("stability_for_plot.csv")
main_ids<-c("access_60_alpha_5_n34","access_60_n33");algorithms<-c("HAC_average","PAM","DBSCAN")
alg_names<-c(HAC_average="平均链接层次聚类",PAM="k-medoids（PAM式SWAP）",DBSCAN="DBSCAN")
cluster_colors<-c(C1="#427C8A",C2="#C58A44",C3="#8C6D9C",C4="#75A16B",C5="#B86166",C6="#A79E55",C7="#6C8BB6",C8="#8F7E74","噪声"="#B7B7B7")
input_names<-function(x)ifelse(grepl("_n34$",x),"完整34节点","无台北33节点")
limits_x<-range(nodes$aeqd_x_km)+c(-500,500);limits_y<-range(nodes$aeqd_y_km)+c(-500,500)
raw_assign<-a[a$family=="rail_time" & a$dataset_id%in%main_ids,]
raw_assign$input<-factor(input_names(raw_assign$dataset_id),levels=c("完整34节点","无台北33节点"))
raw_assign$algorithm<-factor(raw_assign$algorithm,levels=algorithms,labels=unname(alg_names))
geo_labels<-do.call(rbind,lapply(split(raw_assign,interaction(raw_assign$input,raw_assign$algorithm,drop=TRUE)),function(d){
  d$x<-d$geo_x_km/1000;d$y<-d$geo_y_km/1000;d<-place_labels(d);d$lx<-d$lx*1000;d$ly<-d$ly*1000;d
}))
p<-ggplot()+geom_path(data=grid,aes(x_km,y_km,group=line_id),color="#E6E8E9",linewidth=.25)+
  geom_segment(data=geo_labels,aes(geo_x_km,geo_y_km,xend=lx,yend=ly),color="#B5B5B5",linewidth=.2)+
  geom_point(data=raw_assign,aes(geo_x_km,geo_y_km,color=display_cluster,shape=is_noise),size=2.2)+
  geom_point(data=raw_assign[raw_assign$is_medoid,],aes(geo_x_km,geo_y_km),shape=4,size=3,stroke=.6,color="black")+
  geom_text(data=geo_labels,aes(lx,ly,label=city),size=2.6,family=font)+
  facet_grid(input~algorithm)+scale_color_manual(values=cluster_colors,name="显示簇号")+scale_shape_manual(values=c("FALSE"=16,"TRUE"=4),labels=c("FALSE"="普通点","TRUE"="噪声"),name="点型")+
  coord_equal(xlim=limits_x,ylim=limits_y)+labs(title="原始铁路距离上的三种聚类：地理位置对照",subtitle="固定代表设置：k=4；PAM seed42；DBSCAN中位eps/min_samples4",
    x="方位等距投影X（公里）",y="方位等距投影Y（公里）",
    caption="同算法的34/33节点颜色按共同城市最大重叠配准；不同算法同色不代表相同簇。PAM中心另加黑叉，灰叉是DBSCAN噪声。\n聚类依据铁路时间，不是经纬度；城市参考点非站点测量位置，无行政边界；台北有限惩罚不是真实通行时间。")+base+
  theme(strip.text=element_text(size=10),legend.text=element_text(size=8))
save_pair(p,"cluster_raw_geographic_comparison",18,12)

mds<-read_data("MDS_display_coordinates.csv");d<-raw_assign[raw_assign$dataset_id=="access_60_n33",]
d<-merge(d,mds[mds$dataset_id=="access_60_n33",c("node_id","embedding_1","embedding_2")],by="node_id",sort=FALSE)
display_labels<-do.call(rbind,lapply(split(d,d$algorithm),function(z){z<-normalize_display(z);place_labels(z)}))
points<-do.call(rbind,lapply(split(d,d$algorithm),normalize_display))
p<-ggplot(points,aes(x,y))+geom_segment(data=display_labels,aes(xend=lx,yend=ly),color="#B3B3B3",linewidth=.25)+
  geom_point(aes(color=display_cluster,shape=is_noise),size=2.4)+geom_text(data=display_labels,aes(lx,ly,label=city),size=2.9,family=font)+
  facet_wrap(~algorithm,nrow=1)+scale_color_manual(values=cluster_colors,name="显示簇号")+scale_shape_manual(values=c("FALSE"=16,"TRUE"=4),labels=c("FALSE"="普通点","TRUE"="噪声"),name="点型")+
  scale_x_continuous(expand=expansion(mult=.22))+scale_y_continuous(expand=expansion(mult=.12))+
  coord_equal(clip="off")+labs(title="原始铁路距离聚类在同一MDS坐标中的显示",subtitle="连通33节点；所有面板使用同一套MDS点位，聚类标签来自原始距离",x="MDS嵌入维度1（无地理单位）",y="MDS嵌入维度2（无地理单位）",
    caption="这里只用MDS统一显示，未在MDS上重新拟合这些标签；二维表示存在失真。\n颜色在不同算法间不代表同一语义；海口、拉萨等单点簇应结合原始距离、时刻约束及样本范围解释。")+base
save_pair(p,"cluster_raw_on_common_MDS33",18,7)

segments<-read_data("HAC_tree_segments.csv");leaves<-read_data("HAC_tree_leaves.csv");cuts<-read_data("HAC_tree_cuts.csv")
segments$input<-input_names(segments$dataset_id);leaves$input<-input_names(leaves$dataset_id);cuts$input<-input_names(cuts$dataset_id)
max_height<-tapply(segments$yend,segments$input,max)
leaves$label_y<--as.numeric(max_height[leaves$input])*.04
p<-ggplot()+geom_segment(data=segments,aes(x,y,xend=xend,yend=yend),linewidth=.35,color="#555555")+
  geom_hline(data=cuts[!cuts$tie_at_cut,],aes(yintercept=cut_height),linetype="dashed",color="#B86166",linewidth=.4)+
  geom_text(data=leaves,aes(x,label_y,label=city,color=display_cluster),angle=90,hjust=1,size=2.7,family=font)+
  facet_wrap(~input,scales="free",nrow=1)+scale_color_manual(values=cluster_colors,guide="none")+
  scale_x_continuous(breaks=NULL,expand=expansion(mult=c(.02,.03)))+
  scale_y_continuous(breaks=function(x){b<-pretty(x);b[b>=0]},expand=expansion(mult=c(.27,.04)))+
  labs(title="平均链接层次树及固定k=4切分",subtitle="直接使用原始铁路差异度；树和合并高度来自用户实际运行保存记录",x="城市叶节点（树顺序）",y="平均链接合并差异度（除以本输入正距离中位数）",
       caption="虚线表示k=4切分；两面板纵轴各自保留实际高度，完整34节点高层合并受到台北惩罚量级影响。\n较高轮廓系数可能伴随一个大簇和多个单点簇，并不自动证明存在四个均衡经济区域。")+base
save_pair(p,"cluster_HAC_trees",15,7)

main_rep_ids<-reps$representation_id[reps$main_parameter_input]
mainq<-q[q$representation_id%in%main_rep_ids,];mainq$input<-input_names(mainq$dataset_id)
mainq$family<-factor(mainq$family,levels=c("rail_time","MDS","tSNE","UMAP"),labels=c("原始铁路","MDS","t-SNE","UMAP"))
quality<-rbind(transform(mainq,metric="当前输入距离上的轮廓系数",value=silhouette_input),transform(mainq,metric="同一标签在原始铁路距离上的轮廓系数",value=silhouette_original_rail))
alg_colors<-c(HAC_average="#427C8A",PAM="#C58A44",DBSCAN="#8C6D9C")
p<-ggplot(quality,aes(family,value,color=algorithm))+geom_point(position=position_dodge(.4),size=2.5,na.rm=TRUE)+
  facet_grid(metric~input)+scale_color_manual(values=alg_colors,labels=alg_names,name="聚类方法")+
  labs(title="投影中的聚类分数能否保留原铁路结构",subtitle="固定代表划分；同一组标签分别在两种距离中评分",x="聚类输入表示",y="轮廓系数（无量纲）",
       caption="DBSCAN仅评分非噪声节点；覆盖比例另存并在规模图展示。未画出的点表示评分不适用，不是0。\n例如33节点UMAP+DBSCAN：自身轮廓约0.469，原铁路轮廓约0.045；不能只凭投影成团认定客观城市群。")+base
save_pair(p,"cluster_input_vs_rail_quality",12,8)

sizes<-aggregate(node_id~input+algorithm+display_cluster,raw_assign,length);names(sizes)[4]<-"count"
p<-ggplot(sizes,aes(algorithm,count,fill=display_cluster))+geom_col(position="fill",width=.65)+
  facet_wrap(~input)+scale_fill_manual(values=cluster_colors,name="显示簇号")+
  scale_y_continuous(labels=function(x)paste0(round(x*100),"%"),breaks=seq(0,1,.25))+
  labs(title="簇规模与噪声覆盖：避免只看最高分",subtitle="原始铁路距离的固定代表划分；灰色为噪声",x="聚类方法",y="全部节点中的比例",
       caption="完整34节点HAC为31+1+1+1；33节点HAC为30+1+1+1，存在明显规模不均衡。\n原始距离DBSCAN分别保留28/34及28/33节点；不同算法同色仅为显示，不代表同一语义。")+base+
  theme(axis.text.x=element_text(angle=12,hjust=.5,size=9))
save_pair(p,"cluster_sizes_and_noise",12,6)

kdata<-m[m$family=="rail_time" & m$dataset_id%in%main_ids & m$algorithm%in%c("HAC_average","PAM") & grepl("cluster_count",m$tags),]
kdata$input<-input_names(kdata$dataset_id);kdata$largest_share<-kdata$largest_cluster/kdata$assigned_count
klong<-rbind(transform(kdata,metric="原始铁路轮廓系数 ↑",value=silhouette_original_rail),transform(kdata,metric="最大簇占已分配节点比例",value=largest_share))
input_colors<-c("完整34节点"="#427C8A","无台北33节点"="#C58A44")
p<-ggplot(klong,aes(k,value,color=input,group=input))+geom_line(linewidth=.5)+geom_point(size=2.2)+facet_grid(metric~algorithm,scales="free_y")+
  scale_color_manual(values=input_colors,name=NULL)+scale_x_continuous(breaks=c(3,4,5))+
  labs(title="簇数参数的质量与规模权衡",subtitle="原始铁路距离；PAM seed42；其他设置固定",x="要求的簇数k",y="指标值（无量纲）",
       caption="簇数3/4/5均保存；轮廓和簇规模共同解释，不依据一个分数自动选k。\n包含台北时，一个簇可能被结构不可达惩罚节点占用，应与33节点结果比较。")+base
save_pair(p,"cluster_k_sensitivity",11,8)

db<-m[m$family=="rail_time" & m$dataset_id%in%main_ids & m$algorithm=="DBSCAN",];db$input<-input_names(db$dataset_id)
db1<-db[grepl("DBSCAN_epsilon",db$tags),];db1$parameter<-"eps（min_samples固定4）";db1$setting<-as.character(signif(db1$eps,4))
db2<-db[grepl("DBSCAN_min_samples",db$tags),];db2$parameter<-"min_samples（eps固定中位数）";db2$setting<-as.character(db2$min_samples)
db<-rbind(db1,db2)
db$setting<-factor(db$setting,levels=unique(c(as.character(sort(unique(signif(db1$eps,4)))),"3","4","5")))
dblong<-do.call(rbind,lapply(c(n_clusters="非噪声簇数",n_noise="噪声点数",silhouette_original_rail="原铁路轮廓系数 ↑"),function(label){
  key<-names(c(n_clusters="非噪声簇数",n_noise="噪声点数",silhouette_original_rail="原铁路轮廓系数 ↑"))[match(label,c("非噪声簇数","噪声点数","原铁路轮廓系数 ↑"))]
  d<-db;d$metric<-label;d$value<-d[[key]];d
}))
p<-ggplot(dblong,aes(setting,value,color=input,group=input))+geom_line(linewidth=.5,na.rm=TRUE)+geom_point(size=2.1,na.rm=TRUE)+
  facet_grid(metric~parameter,scales="free")+scale_color_manual(values=input_colors,name=NULL)+
  labs(title="DBSCAN参数、噪声与评分适用性",subtitle="eps源于第3其他点距离分位数；min_samples包括自身",x="当前参数值（eps为归一化距离）",y="数量或轮廓系数",
       caption="没有轮廓点的设置可能为单簇或全部噪声，状态表保留原因，未填0。\n同一分位数在不同输入中不一定得到同一eps；提高保留覆盖与提高条件评分需要同时考虑。")+base+
  theme(axis.text.x=element_text(angle=30,hjust=1,size=8))
save_pair(p,"cluster_DBSCAN_sensitivity",12,9)

ps<-stable[stable$comparison=="PAM_seed",];ps$input<-input_names(ps$dataset_id)
ps$family<-factor(ps$family,levels=c("rail_time","MDS","tSNE","UMAP"),labels=c("原始铁路","MDS","t-SNE","UMAP"))
set.seed(42)
p<-ggplot(ps,aes(family,ari_common_assigned,color=input,shape=input))+geom_point(position=position_jitterdodge(jitter.width=.08,dodge.width=.35),size=2.4)+
  scale_color_manual(values=input_colors,name=NULL)+scale_shape_discrete(name=NULL)+
  labs(title="PAM聚类初始化种子的稳定性",subtitle="k=4；seed=0/42/2026，每份输入3个两两配对",x="聚类输入表示",y="共同已分配节点上的ARI（无量纲）",
       caption="这里固定投影坐标，只改变PAM初始化；不与投影自身的种子变化混合。\n原始铁路两种输入的三对ARI均为1，只说明所测种子划分一致，不证明全局最优或无参数敏感性。")+base
save_pair(p,"cluster_PAM_seed_stability",10,5.7)

c<-comparison[comparison$comparison=="original_rail_vs_embedding" & comparison$main_b,]
c$input<-input_names(c$dataset_b);c$family_b<-factor(c$family_b,levels=c("MDS","tSNE","UMAP"),labels=c("MDS","t-SNE","UMAP"))
clong<-rbind(transform(c,metric="ARI：噪声按一个标签",value=ari_including_noise_as_label),
             transform(c,metric="ARI：双方共同非噪声",value=ari_common_assigned),transform(c,metric="共同非噪声节点比例",value=common_assigned_fraction))
p<-ggplot(clong,aes(family_b,value,color=algorithm))+geom_point(position=position_dodge(.4),size=2.5,na.rm=TRUE)+facet_grid(metric~input)+
  scale_color_manual(values=alg_colors,labels=alg_names,name="聚类方法")+
  labs(title="原始铁路划分与嵌入划分的一致性",subtitle="比较同算法固定代表设置，按共同城市对齐标签",x="嵌入表示",y="一致性或比例（无量纲）",
       caption="ARI不受簇号排列影响；两种噪声口径同时报告，并展示共同保留比例。\n缺失点表示共同非噪声划分不满足评分条件，不代表一致性为0。投影参数及种子变化的其他比较另存。")+base
save_pair(p,"cluster_raw_embedding_agreement",12,9)

s<-comparison[comparison$comparison=="Taipei_vs_no_Taipei_common33",]
s$access<-factor(s$access_b,levels=c(30,60,90),labels=c("接驳30分钟","接驳60分钟","接驳90分钟"))
slong<-rbind(transform(s,metric="共同33节点ARI（噪声作标签）",value=ari_including_noise_as_label),transform(s,metric="双方共同非噪声比例",value=common_assigned_fraction))
p<-ggplot(slong,aes(alpha_b,value,color=access,group=access))+geom_line(linewidth=.5)+geom_point(size=2.2)+facet_grid(metric~algorithm)+
  scale_color_manual(values=c("#427C8A","#C58A44","#8C6D9C"),name=NULL)+scale_x_continuous(breaks=c(2,5,10))+
  labs(title="台北惩罚与澳门接驳下的划分对照",subtitle="完整34节点与同接驳水平的无台北33节点，只比较共同33个城市",x="台北惩罚倍数alpha",y="一致性或覆盖比例",
       caption="线重合说明所考察配置的划分比较相同，不能扩展为所有参数均无影响。\nk固定时台北可能单独占一个簇；普通数据缺失未使用惩罚，澳门接驳为假设。")+base
save_pair(p,"cluster_special_region_sensitivity",14,8)
writeLines(c(R.version.string,"Plotting verified user198 cluster configurations, no clustering fits in R.",
 "Display colors only matched within algorithm to raw33 reference by positive-overlap Hungarian assignment; original labels unchanged.",
 "All figures titled. NA metrics remain unavailable; noise and singleton caveats retained.",
 "r-academic-plots helper/shared style used; private book originals unavailable; no new R installs."),file.path(output,"R_figure_provenance.txt"),useBytes=TRUE)
cat("CLUSTER_R_FIGURES_COMPLETED\n")
