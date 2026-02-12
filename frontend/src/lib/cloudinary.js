export function openCloudinaryWidget({ cloudName, uploadPreset, folder = 'productos' } = {}) {
  return new Promise((resolve, reject) => {
    if (!cloudName || !uploadPreset) {
      reject(new Error('Cloudinary no configurado: falta cloudName o uploadPreset'));
      return;
    }
    const widgetFactory = window.cloudinary && window.cloudinary.createUploadWidget;
    if (!widgetFactory) {
      reject(new Error('Cloudinary widget no disponible'));
      return;
    }

    const widget = widgetFactory(
      {
        cloudName,
        uploadPreset,
        folder,
        multiple: false,
        sources: ['local', 'url', 'camera'],
      },
      (error, result) => {
        if (error) {
          reject(error);
          return;
        }
        if (result?.event === 'success') {
          resolve(result.info?.secure_url || '');
        }
      }
    );

    widget.open();
  });
}
