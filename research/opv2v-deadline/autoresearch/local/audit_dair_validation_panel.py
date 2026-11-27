"""Inventory DAIR validation inputs and lock any availability-based subset before inference."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("dataset", type=Path)
parser.add_argument("report", type=Path)
parser.add_argument("--split", required=True, type=Path,
                    help="Existing frozen DAIR val.json")
args = parser.parse_args()
data = args.dataset.resolve()
split_bytes = args.split.read_bytes()
split_sha256 = hashlib.sha256(split_bytes).hexdigest()
if split_sha256 != "a0993520f5f91af282a96a2d542f3d837434b7a68392636f90bff050883fd832":
    parser.error("validation split SHA-256 does not match frozen DAIR val.json")
requested = json.loads(split_bytes)
if len(requested) != 1783 or len(set(requested)) != 1783:
    parser.error("expected exactly 1,783 unique validation frame IDs")
required_tables = ("cooperative/data_info.json", "infrastructure-side/data_info.json",
                   "vehicle-side/data_info.json")
missing_tables = [name for name in required_tables if not (data/name).is_file()]
report = dict(dataset=str(data), split_sha256=split_sha256,
              requested_frames=len(requested), missing_tables=missing_tables, ready=[], excluded=[])
if not missing_tables:
    cooperative, infrastructure, vehicle = [json.loads((data/name).read_text()) for name in required_tables]
    pairs = {Path(r["vehicle_image_path"]).stem:r for r in cooperative}
    side_rows = [{Path(r["image_path"]).stem:r for r in source if r.get("image_path")}
                 for source in (vehicle,infrastructure)]
    for fid in requested:
        if fid not in pairs:
            report["excluded"].append({"frame":fid,"reason":"no cooperative metadata"})
            continue
        pair = pairs[fid]
        inf_id = Path(pair["infrastructure_image_path"]).stem
        ego_info, inf_info = side_rows[0].get(fid,{}), side_rows[1].get(inf_id,{})
        required = [pair[k] for k in ("vehicle_image_path","infrastructure_image_path",
                                     "vehicle_pointcloud_path","infrastructure_pointcloud_path")]
        label = pair["cooperative_label_path"]
        required += [label,label.replace("label_world","label_world_backup"),
                     f"vehicle-side/label/lidar/{fid}.json",
                     f"vehicle-side/label/lidar_backup/{fid}.json",
                     f"infrastructure-side/label/virtuallidar/{inf_id}.json"]
        for side, id_, calibrations in (
            ("vehicle-side",fid,("lidar_to_novatel","novatel_to_world","lidar_to_camera","camera_intrinsic")),
            ("infrastructure-side",inf_id,("virtuallidar_to_world","virtuallidar_to_camera","camera_intrinsic")),
        ):
            required.extend(f"{side}/calib/{calibration}/{id_}.json" for calibration in calibrations)
        missing = [name for name in required if not name or not (data/name).is_file()]
        scene = inf_info.get("batch_id")
        detail = dict(frame=fid, infrastructure_frame=inf_id, scene=scene,
                      timestamp=ego_info.get("pointcloud_timestamp",ego_info.get("image_timestamp")),
                      official_occlusion_exists=(data/label.replace("label_world","label_world_with_occlusion")).is_file())
        if missing or scene is None or detail["timestamp"] is None:
            report["excluded"].append(dict(detail,missing=missing,
                                           metadata_incomplete=scene is None or detail["timestamp"] is None))
        else:
            report["ready"].append(detail)
    report["ready"].sort(key=lambda r: (str(r["scene"]),int(r["timestamp"]),r["frame"]))
report["ready_by_scene"]=dict(Counter(str(row["scene"]) for row in report["ready"]))
args.report.parent.mkdir(exist_ok=True,parents=True)
with args.report.open("x", encoding="utf-8") as output:
    json.dump(report, output, indent=2)
    output.write("\n")
print(f'{len(report["ready"])}/{len(requested)} frames available across {len(report["ready_by_scene"])} scenes')
