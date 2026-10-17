(function () {
  const btn = document.getElementById("pick-folder");
  if (!btn) return;

  btn.addEventListener("click", async function () {
    try {
      const resp = await fetch("/api/v1/settings/google/picker-config", {
        credentials: "same-origin",
      });
      if (!resp.ok) {
        alert("Не удалось получить токен для Picker");
        return;
      }
      const cfg = await resp.json();
      gapi.load("picker", function () {
        const view = new google.picker.DocsView(
          google.picker.ViewId.FOLDERS
        );
        view.setSelectFolderEnabled(true);
        const picker = new google.picker.PickerBuilder()
          .addView(view)
          .setOAuthToken(cfg.access_token)
          .setDeveloperKey(cfg.api_key)
          .setAppId(cfg.app_id)
          .setCallback(async function (data) {
            if (data.action !== google.picker.Action.PICKED) return;
            const folder = data.docs[0];
            const csrf = document
              .querySelector('meta[name="csrf-token"]')
              .getAttribute("content");
            const r = await fetch("/api/v1/settings/google/folder", {
              method: "PUT",
              credentials: "same-origin",
              headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrf,
              },
              body: JSON.stringify({ folder_id: folder.id }),
            });
            if (r.ok) {
              location.href = "/settings?flash=Папка+выбрана";
            } else {
              alert("Не удалось сохранить папку");
            }
          })
          .build();
        picker.setVisible(true);
      });
    } catch (e) {
      alert("Ошибка Picker: " + e);
    }
  });
})();
