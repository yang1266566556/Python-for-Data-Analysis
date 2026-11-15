# Independent R script; called by Python, never pasted as Python source.
# Uses the available r-academic-plots helper; no package installation.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3L) stop("Expected project root, verified audit directory, output directory")
root <- args[[1]]; audit_dir <- args[[2]]; output_dir <- args[[3]]
if (!requireNamespace("ggplot2", quietly=TRUE)) stop("ggplot2 is missing")
suppressPackageStartupMessages(library(ggplot2))
helper <- "C:/Users/yang/.codex/skills/r-academic-plots/scripts/academic_plot_helpers.R"
if (!file.exists(helper)) stop("Academic plot helper not available")
source(helper, encoding="UTF-8")
font_family <- "Microsoft YaHei"
read_utf8 <- function(path) read.csv(path, fileEncoding="UTF-8-BOM", check.names=FALSE, stringsAsFactors=FALSE)
processed <- file.path(root, "data/processed/user_stage1c_v2_20261113_132207_325427")
quality <- read_utf8(file.path(audit_dir, "query_quality_verified.csv"))
direct <- read_utf8(file.path(processed, "direct_screen_34x34_long.csv"))
nodes <- read_utf8(file.path(processed, "nodes_34.csv"))
dir.create(output_dir, recursive=TRUE, showWarnings=FALSE)
base_theme <- theme_academic(base_size=10, base_family=font_family) +
  theme(plot.title=element_text(size=14, face="bold", margin=margin(b=8)),
        plot.subtitle=element_text(size=9, color="#555555", margin=margin(b=12)),
        plot.caption=element_text(size=8, color="#555555", hjust=0, margin=margin(t=12)),
        legend.title=element_text(size=9), legend.text=element_text(size=8),
        plot.margin=margin(14,16,14,14))

# User requires all delivered assignment figures to have titles and axis labels.
# This requirement takes precedence over the skill's clean-version default.
save_plot <- function(plot, name, width, height) {
  png_path <- file.path(output_dir, paste0(name, ".png"))
  pdf_path <- file.path(output_dir, paste0(name, ".pdf"))
  ggsave(png_path, plot=plot, width=width, height=height, units="in", dpi=300, bg="white")
  ggsave(pdf_path, plot=plot, width=width, height=height, units="in", device=grDevices::cairo_pdf, bg="white")
  cat(png_path, "\n", pdf_path, "\n", sep="")
}

counts <- as.data.frame(table(quality$status), stringsAsFactors=FALSE)
names(counts) <- c("status", "count")
labels <- c(validated_records="记录检查通过", no_direct_train_returned_not_unreachable="未返回直达记录",
            partial_timetable_unavailable="部分时刻未知", partial_station_metadata_unresolved="部分站码待核验")
counts$label <- unname(labels[counts$status])
counts <- counts[order(counts$count), ]
counts$label <- factor(counts$label, levels=counts$label)
p1 <- ggplot(counts, aes(x=label, y=count)) +
  geom_col(width=0.62, fill="#247A80") +
  geom_text(aes(label=count), hjust=-0.25, family=font_family, size=3.5) +
  coord_flip(clip="off") + scale_y_continuous(expand=expansion(mult=c(0,0.15))) +
  labs(title="图1-1｜995组铁路查询的数据质量", subtitle="2026-11-18；992个核心城市有向对＋3组辅助接入查询",
       x="查询状态", y="查询组数（组）", caption="来源：用户实际采集的12306响应。空直达结果不等于铁路不可达。") + base_theme
save_plot(p1, "fig1_1_query_quality", 8.5, 4.8)

direct$time <- suppressWarnings(as.numeric(direct$observed_direct_min_minutes))
direct$to_city <- factor(direct$to_city, levels=nodes$representative_city)
direct$from_city <- factor(direct$from_city, levels=rev(nodes$representative_city))
direct$missing_kind <- NA_character_
direct$missing_kind[grepl("no_direct_record_returned",direct$status)] <- "未返回直达"
direct$missing_kind[grepl("special_region",direct$status)] <- "特殊地区待核验"
direct$missing_kind[grepl("unknown_timetable_no",direct$status)] <- "时刻未知"
direct$missing_kind[grepl("returned_stations_outside",direct$status)] <- "站点范围待定"
unknown <- direct[is.na(direct$time), ]
known <- direct[!is.na(direct$time), ]
p2 <- ggplot(direct, aes(x=to_city, y=from_city)) +
  geom_tile(fill="#F1F1F1", color="white", linewidth=0.15) +
  geom_tile(data=known, aes(fill=time), color="white", linewidth=0.15) +
  geom_point(data=unknown, aes(shape=missing_kind), size=1.1, color="#777777", stroke=0.35) +
  scale_fill_gradientn(colors=academic_palette("bluegreen", 128), name="观测历时\n（分钟）") +
  scale_shape_manual(values=c("未返回直达"=4,"特殊地区待核验"=0,"时刻未知"=2,"站点范围待定"=3), name="空值原因", drop=FALSE) +
  coord_fixed() +
  labs(title="图1-2｜34节点直达服务观测历时", subtitle="有向关系；原83站候选范围；颜色为已观测直达历时，尚未计入中转",
       x="到达代表城市", y="出发代表城市",
       caption="空值保留明确状态，不作惩罚填补。含部分未知车次的单元格只显示已知记录最小值。\n这是直达查询诊断图；澳门、台北接入待核验，对角线为0。") +
  base_theme + theme(axis.text.x=element_text(angle=90,hjust=1,vjust=0.5,size=7),
                     axis.text.y=element_text(size=7), axis.ticks=element_blank(),
                     axis.line=element_blank(), legend.key.height=grid::unit(0.5,"cm"))
save_plot(p2, "fig1_2_direct_service_heatmap", 11.2, 10)

finite <- direct[direct$from_node != direct$to_node & !is.na(direct$time), ]
p3 <- ggplot(finite, aes(x=time)) +
  geom_histogram(bins=30, boundary=0, closed="left", fill="#4C9899", color="white", linewidth=0.35) +
  labs(title="图1-3｜已知直达服务最小历时的分布", subtitle=paste0("有向城市对 n = ", nrow(finite), "；2026-11-18；不含对角线"),
       x="已观测直达最小历时（分钟）", y="有向城市对数量（对）",
       caption="未返回直达、时刻未知及特殊地区待核验项不纳入直方图，未将其当作0。\n每个有向城市对仅取候选站范围内的已知直达记录最小值，不代表完整最短行程。") + base_theme
save_plot(p3, "fig1_3_observed_direct_time_distribution", 8.5, 5)
writeLines(c(R.version.string, paste("ggplot2", as.character(packageVersion("ggplot2"))),
             paste("font", font_family), paste("helper", helper)), file.path(output_dir,"R_plot_environment.txt"), useBytes=TRUE)
cat("QUALITY_PLOTS_COMPLETED\n")
