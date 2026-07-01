use std::path::Path;

include!(concat!(env!("OUT_DIR"), "/generated_assets.rs"));

pub fn asset_id_for_asset_path(asset_root: &str, relative_path: &str) -> i32 {
    asset_id_for_normalized_path(&format!(
        "{}/{}",
        asset_root.trim_end_matches('/'),
        relative_path.trim_start_matches('/')
    ))
}

pub fn asset_id_for_path(path: &Path) -> Option<i32> {
    let path = path.to_str()?.replace('\\', "/");
    Some(asset_id_for_normalized_path(&path))
}

pub fn asset_id_for_normalized_path(path: &str) -> i32 {
    let normalized = path.strip_prefix("./").unwrap_or(path);
    let mut hash = 0x811c9dc5u32;
    for byte in normalized.as_bytes() {
        hash ^= u32::from(*byte);
        hash = hash.wrapping_mul(16_777_619);
    }
    ((hash % 10_000) + 1) as i32
}
