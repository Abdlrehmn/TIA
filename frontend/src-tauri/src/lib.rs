#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![get_api_token])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while building tauri application");
}

#[tauri::command]
fn get_api_token() -> Result<String, String> {
    let token = std::env::var("TIA_API_TOKEN")
        .map_err(|_| "The local API session is not configured.".to_string())?;
    if token.len() < 43 || !token.is_ascii() {
        return Err("The local API session is not configured.".to_string());
    }
    Ok(token)
}
