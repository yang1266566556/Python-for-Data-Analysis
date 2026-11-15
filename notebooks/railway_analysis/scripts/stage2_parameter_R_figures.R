# Plot verified user-run experiments. No embeddings or clustering fitted in R.
args<-commandArgs(trailingOnly=TRUE);if(length(args)!=1L)stop("Expected config")
source(args[[1]],encoding="UTF-8")
suppressPackageStartupMessages(library(ggplot2));suppressPackageStartupMessages(library(patchwork))
source("C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R",encoding="UTF-8")
source(file.path(scripts,"stage2_plot_style.R"),encoding="UTF-8")
dir.create(output,recursive=TRUE,showWarnings=FALSE)
read_data<-function(n)read.csv(file.path(input,n),fileEncoding="UTF-8-BOM",check.names=FALSE,stringsAsFactors=FALSE)
m<-read_data("experiment_metrics.csv");comparisons<-read_data("parameter_comparison.csv")
seeds<-read_data("seed_stability_pairs.csv");sq<-read_data("representative_seed_quality.csv");coords<-read_data("coordinates_all.csv")
main_ids<-c("access_60_alpha_5_n34","access_60_n33")
scope<-function(id)ifelse(grepl("_n34$",id),"34节点拟合：评估连通33点","33节点单独拟合")
quality_keys<-c(network_only_external_scale_fitted_stress1="外部stress ↓",network_only_distance_spearman="距离秩相关 ↑",
                network_only_neighbor_overlap_k5="5近邻重叠率 ↑",network_only_trustworthiness_k5="5近邻可信度 ↑")
group_colors<-c("34节点拟合：评估连通33点"="#427C8A","33节点单独拟合"="#B47B44")
quality_long<-function(d)do.call(rbind,lapply(names(quality_keys),function(k) {
  out<-d;out$value<-out[[k]];out$quality<-unname(quality_keys[k]);out
}))
tags<-c("tSNE_perplexity","tSNE_iterations","UMAP_neighbors","UMAP_min_dist")
keys<-c("perplexity","max_iter","n_neighbors","min_dist")
labels<-c("t-SNE：perplexity","t-SNE：迭代上限","UMAP：邻居数","UMAP：min_dist")
ofat<-do.call(rbind,lapply(seq_along(tags),function(i) {
  d<-comparisons[comparisons$comparison==tags[i],];d$parameter<-labels[i];d$setting<-as.character(d[[keys[i]]]);d
}))
ofat$parameter<-factor(ofat$parameter,levels=labels);ofat$scope<-scope(ofat$dataset_id)
ofat$setting<-factor(ofat$setting,levels=unique(unlist(lapply(seq_along(tags),function(i)sort(unique(as.numeric(ofat$setting[ofat$parameter==labels[i]])))))))
long<-quality_long(ofat);long$quality<-factor(long$quality,levels=unname(quality_keys))
p<-ggplot(long,aes(setting,value,color=scope,group=scope))+geom_line(linewidth=.5)+geom_point(size=2)+
  facet_grid(quality~parameter,scales="free")+scale_color_manual(values=group_colors,name=NULL)+
  labs(title="单参数变化对降维质量的影响",subtitle="其他参数保持基线；seed=42；两种输入均报告连通网络内部指标",x="当前参数取值",y="指标值（无量纲）",
       caption="每个参数比较三个取值；面板内可比较两种输入，纵轴按指标分别设置。\n大惩罚节点不计入本图评分单元格；参数最优值不能脱离参考距离、其他指标和随机稳定性单独判断。")+base
save_pair(p,"parameter_ofat_quality",14,10)

mds<-comparisons[comparisons$comparison%in%c("MDS_metric","MDS_n_init"),]
mds$parameter<-ifelse(mds$comparison=="MDS_metric","度量设置","初始化次数")
mds$setting<-ifelse(mds$comparison=="MDS_metric",ifelse(mds$model=="MDS","度量","非度量"),as.character(mds$n_init))
mds$scope<-scope(mds$dataset_id);long<-quality_long(mds);long$quality<-factor(long$quality,levels=unname(quality_keys))
p<-ggplot(long,aes(setting,value,color=scope,group=scope))+geom_line(linewidth=.5)+geom_point(size=2)+
  facet_grid(quality~parameter,scales="free")+scale_color_manual(values=group_colors,name=NULL)+
  labs(title="MDS度量设置与初始化次数的比较",subtitle="max_iter=1000；seed=42；每次使用独立的预计算距离副本",x="设置",y="统一外部指标（无量纲）",
       caption="度量/非度量均比较全部二元设置；n_init比较1、4、8，其他设置固定。\n此处是相同原距离上的外部指标；非度量MDS内部以单调差异度计算的stress另存，不能混为同一损失。")+base
save_pair(p,"parameter_MDS_settings",10,9)

stability_keys<-c(procrustes_disparity="全部节点：Procrustes差异 ↓",network_only_procrustes_disparity="连通部分：Procrustes差异 ↓",
                  network_only_embedding_neighbor_overlap_k5="连通部分：种子间5近邻一致率 ↑")
stability<-do.call(rbind,lapply(names(stability_keys),function(k){d<-seeds;d$value<-d[[k]];d$comparison<-stability_keys[k];d}))
stability$scope<-ifelse(grepl("_n34$",stability$dataset_id),"完整34节点输入","无台北33节点输入");stability$model<-factor(stability$model,levels=c("MDS","MDS_nonmetric","tSNE","UMAP"),labels=c("MDS","非度量MDS","t-SNE","UMAP"))
set.seed(42)
p<-ggplot(stability,aes(model,value,color=scope,shape=scope))+geom_point(position=position_jitterdodge(jitter.width=.10,dodge.width=.4),size=2.4)+
  facet_wrap(~comparison,nrow=1,scales="free_y")+scale_color_manual(values=c("完整34节点输入"="#427C8A","无台北33节点输入"="#B47B44"),name=NULL)+scale_shape_discrete(name=NULL)+
  labs(title="三个随机种子之间的形状与邻域稳定性",subtitle="种子0、42、2026；每组3个两两配对；代表性参数固定",x="模型",y="指标值（无量纲）",
       caption="每点表示一对种子的比较，配对并非相互独立的统计重复；未构造显著性检验。\nProcrustes已允许平移、旋转、反射和尺度调整。完整34节点几何可能被台北主导，须同时查看连通33点。")+base+
  theme(axis.text.x=element_text(angle=20,hjust=1))
save_pair(p,"parameter_seed_stability",15,5.5)

seed_long<-do.call(rbind,lapply(c("network_only_external_scale_fitted_stress1","network_only_trustworthiness_k5"),function(k) {
  d<-sq;d$value<-d[[paste0(k,"_mean")]];d$sd<-d[[paste0(k,"_sd")]];d$quality<-quality_keys[k];d
}))
seed_long$scope<-scope(seed_long$dataset_id)
seed_long$model<-factor(seed_long$model,levels=c("MDS","MDS_nonmetric","tSNE","UMAP"),labels=c("MDS","非度量MDS","t-SNE","UMAP"))
p<-ggplot(seed_long,aes(model,value,color=scope))+geom_errorbar(aes(ymin=value-sd,ymax=value+sd),width=.12,position=position_dodge(.35),linewidth=.45)+
  geom_point(position=position_dodge(.35),size=2.4)+facet_wrap(~quality,scales="free_y")+scale_color_manual(values=group_colors,name=NULL)+
  labs(title="代表性参数下三种子的质量均值与波动",subtitle="只对相同参数配置汇总；评估连通网络内部",x="模型",y="均值 ± 样本标准差（无量纲）",
       caption="误差线是3种子的描述性标准差，不是置信区间；不将不同参数配置混入随机波动。\n质量指标接近不意味着二维形状完全稳定，应结合种子间Procrustes及近邻一致性。")+base
save_pair(p,"parameter_seed_quality",11,5.5)

sens<-m[grepl("special_region_sensitivity",m$tags),]
pen<-sens[sens$dataset_id%in%paste0("access_60_alpha_",c(2,5,10),"_n34"),]
pen$alpha<-as.numeric(sub(".*_alpha_([0-9]+)_.*","\\1",pen$dataset_id))
pen_keys<-c(external_scale_fitted_stress1="全部节点：外部stress ↓",network_only_external_scale_fitted_stress1="连通部分：外部stress ↓")
pen_long<-do.call(rbind,lapply(names(pen_keys),function(k){d<-pen;d$value<-d[[k]];d$comparison<-pen_keys[k];d}))
control<-sens[sens$dataset_id=="access_60_n33",]
control_long<-do.call(rbind,lapply(names(pen_keys),function(k){d<-control;d$value<-d[[k]];d$comparison<-pen_keys[k];d}))
alg_colors<-c("MDS"="#427C8A","tSNE"="#B47B44","UMAP"="#916380")
p<-ggplot(pen_long,aes(alpha,value,color=algorithm))+geom_hline(data=control_long,aes(yintercept=value,color=algorithm),linetype="dashed",linewidth=.4)+
  geom_line(linewidth=.55)+geom_point(size=2.4)+facet_wrap(~comparison,nrow=1)+scale_color_manual(values=alg_colors,name="算法")+
  scale_x_continuous(breaks=c(2,5,10))+labs(title="台北惩罚量级对全局与连通部分指标的影响",subtitle="澳门接驳60分钟；P=alpha×4555；seed=42",x="惩罚倍数alpha",y="外部尺度拟合stress（无量纲）",
       caption="实线为完整34节点拟合；同色虚线是无台北33节点对照。普通缺失未使用惩罚。\n极大惩罚不是实测旅行时间；总stress随惩罚变化，不能据此认定连通网络结构同步改善。")+base
save_pair(p,"parameter_penalty_sensitivity",11,5.5)

acc<-sens[sens$dataset_id%in%c(paste0("access_",c(30,60,90),"_alpha_5_n34"),paste0("access_",c(30,60,90),"_n33")),]
acc$access<-as.numeric(sub("access_([0-9]+)_.*","\\1",acc$dataset_id));acc$input<-ifelse(acc$node_count==34,"完整34节点拟合","无台北33节点拟合")
acc_long<-do.call(rbind,lapply(c("network_only_external_scale_fitted_stress1","network_only_neighbor_overlap_k5"),function(k){d<-acc;d$value<-d[[k]];d$comparison<-quality_keys[k];d}))
p<-ggplot(acc_long,aes(access,value,color=algorithm,linetype=input,shape=input))+geom_line(linewidth=.5)+geom_point(size=2.2)+
  facet_wrap(~comparison,scales="free_y")+scale_color_manual(values=alg_colors,name="算法")+scale_linetype_discrete(name="输入")+scale_shape_discrete(name="输入")+
  scale_x_continuous(breaks=c(30,60,90))+labs(title="澳门接驳假设的敏感性",subtitle="台北alpha=5；seed=42；仅评分连通网络内部",x="澳门接驳假设（分钟）",y="指标值（无量纲）",
       caption="30/60/90分钟均为模型假设，包含口岸开放约束；不代表已实测的步行或通关时间。\n部分曲线重叠表示这些设置下数值相近，不能扩大为所有接驳情景均无影响。")+base
save_pair(p,"parameter_access_sensitivity",11,5.7)

comb<-m[m$dataset_id%in%main_ids & m$seed==42 & m$algorithm%in%c("tSNE","UMAP"),]
comb<-comb[(comb$algorithm=="tSNE" & ((comb$perplexity==5 & comb$max_iter==500)|(comb$perplexity==10 & comb$max_iter==1000)|(comb$perplexity==20 & comb$max_iter==2000)))|
           (comb$algorithm=="UMAP" & ((comb$n_neighbors==5 & comb$min_dist==0)|(comb$n_neighbors==10 & comb$min_dist==.1)|(comb$n_neighbors==20 & comb$min_dist==.5))),]
comb$setting<-ifelse(comb$algorithm=="tSNE",paste(comb$perplexity,comb$max_iter,sep=" / "),paste(comb$n_neighbors,comb$min_dist,sep=" / "));comb$scope<-scope(comb$dataset_id)
comb$setting<-factor(comb$setting,levels=c("5 / 500","10 / 1000","20 / 2000","5 / 0","10 / 0.1","20 / 0.5"))
comb_long<-quality_long(comb);comb_long<-comb_long[comb_long$quality%in%quality_keys[c(1,3)],]
p<-ggplot(comb_long,aes(setting,value,color=scope,group=scope))+geom_line(linewidth=.5)+geom_point(size=2.3)+
  facet_grid(quality~algorithm,scales="free")+scale_color_manual(values=group_colors,name=NULL)+
  labs(title="少量参数组合的探索性对照",subtitle="t-SNE横轴：perplexity / 迭代；UMAP横轴：邻居数 / min_dist",x="组合设置",y="连通部分外部指标（无量纲）",
       caption="每种算法仅比较基线及两组预设组合，不是完整交叉实验。\n两项参数同时改变时，不能把差异单独归因于其中一项；单参数证据另见OFAT图。")+base
save_pair(p,"parameter_selected_combinations",11,7)

align_display_to_baseline<-function(a,reference) {
  reference<-reference[match(a$node_id,reference$node_id),]
  x<-as.matrix(a[,c("embedding_1","embedding_2")]);y<-as.matrix(reference[,c("embedding_1","embedding_2")])
  xc<-scale(x,center=TRUE,scale=FALSE);yc<-scale(y,center=TRUE,scale=FALSE)
  decomposition<-svd(t(xc)%*%yc);rotation<-decomposition$u%*%t(decomposition$v)
  transformed<-xc%*%rotation*(sum(decomposition$d)/sum(xc^2))
  a$embedding_1<-transformed[,1];a$embedding_2<-transformed[,2];a
}
for(i in seq_along(c(tags,"MDS_metric"))) {
  tag<-c(tags,"MDS_metric")[i]
  d<-coords[coords$dataset_id=="access_60_n33" & coords$seed==42 & grepl(tag,coords$tags,fixed=TRUE),]
  runs<-unique(d$run_id);key<-if(i<=4)keys[i] else "model"
  if(i<=4)runs<-runs[order(sapply(runs,function(n)as.numeric(d[d$run_id==n,key][1])))]
  reference<-if(i<=4)d[d[[key]]==c(10,1000,10,.1)[i],] else d[d$model=="MDS",]
  plots<-lapply(seq_along(runs),function(j){
    a<-d[d$run_id==runs[j],];setting<-if(i==5)if(a$model[1]=="MDS")"度量MDS" else "非度量MDS" else paste0(keys[i]," = ",a[[key]][1])
    a<-align_display_to_baseline(a,reference)
    q<-panel(a,setting,"连通33节点；seed=42")
    if(j>1)q<-q+guides(color="none")
    q
  })
  p<-wrap_plots(plots,nrow=1,widths=rep(1,length(plots)),guides="collect")+
    plot_annotation(title=if(i<=4)paste0(labels[i],"：实际二维布局对照") else "度量与非度量MDS：实际二维布局对照",
      caption="同一冻结输入；面板先以旋转/反射/尺度变换对齐该算法基线，再作显示归一化；坐标无地理单位，不是分钟。\n颜色只区分澳门接驳处理方式；不把t-SNE/UMAP图中的空白或簇间距离直接解释为实际交通距离。")
  p<-p & theme(legend.position="bottom",plot.title=element_text(family=font,size=13,face="bold"),plot.subtitle=element_text(family=font,size=9),plot.caption=element_text(family=font,size=9,hjust=0))
  save_pair(p,paste0("parameter_layout_",tag),if(length(plots)==3)18 else 12,7)
}
writeLines(c(R.version.string,paste("ggplot2",packageVersion("ggplot2")),paste("patchwork",packageVersion("patchwork")),
 "Authenticated user82 configurations only; no scientific fitting in R.","Used r-academic-plots helper and verified shared display style; private book originals unavailable.",
 "All figures titled per user request. Error bars are descriptive three-seed SD; pairwise seed comparisons not independent replicates."),file.path(output,"R_figure_provenance.txt"),useBytes=TRUE)
cat("PARAMETER_R_FIGURES_COMPLETED\n")
