const strings = {
  en: {capture:'Send downloads to HDM', download:'Download this page or video', video:'Show video download button',
    streams:'Detected video streams', downloadStream:'Download selected stream', session:"Use this site's signed-in session",
    settings:'Settings', permissionDenied:'Permission was not granted.',
    captureEnabled:'New downloads will be sent to HDM.', captureDisabled:'New downloads will stay in the browser.',
    offline:'HDM is unavailable. Open the app; the extension will reconnect automatically.',
    working:'Working…', connected:'Connected to HDM.', sent:'Sent to HDM.',
    connectionTitle:'Browser connection', connectionHelp:'The extension connects automatically. Manage download capture in the HDM popup.',
},
  vi: {capture:'Chuyển lượt tải sang HDM', download:'Tải trang hoặc video hiện tại', video:'Hiện nút tải trên video',
    streams:'Luồng video trên trang', downloadStream:'Tải luồng đã chọn', session:'Dùng phiên đăng nhập của trang này',
    settings:'Thiết lập', permissionDenied:'Chưa được cấp quyền.',
    captureEnabled:'Lượt tải mới sẽ chuyển sang HDM.', captureDisabled:'Lượt tải mới sẽ do trình duyệt tải.',
    offline:'HDM chưa sẵn sàng. Hãy mở app; tiện ích sẽ tự kết nối lại.',
    working:'Đang xử lý…', connected:'Đã kết nối HDM.', sent:'Đã gửi tới HDM.',
    connectionTitle:'Kết nối trình duyệt', connectionHelp:'Tiện ích tự kết nối. Bật hoặc tắt chuyển lượt tải trong bảng điều khiển HDM.',
},
};

export function localize(settings) {
  const language = settings.language === 'vi' ? 'vi' : 'en';
  document.documentElement.lang = language;
  document.documentElement.dataset.theme = ['light','dark'].includes(settings.theme) ? settings.theme : 'system';
  const text = key => strings[language][key] || key;
  for (const element of document.querySelectorAll('[data-i18n]')) element.textContent = text(element.dataset.i18n);
  return text;
}
