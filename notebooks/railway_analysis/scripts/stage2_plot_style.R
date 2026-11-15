# Shared verified R display style; no scientific model fitting.
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
