# 📦 Instalar el APK en el móvil

El archivo **`corrector-examenes.apk`** (en esta misma carpeta) es la app
Android del Corrector de Exámenes. Es un envoltorio (TWA) que abre a pantalla
completa la PWA publicada en
`https://upocuantitativo.github.io/corrector-examenes/`.

## Instalación

1. Pasa `corrector-examenes.apk` al móvil (cable USB, Google Drive, correo,
   WhatsApp a ti mismo, etc.).
2. En el móvil, abre el archivo. Android pedirá permitir **«instalar apps de
   orígenes desconocidos»** para tu navegador/gestor de archivos: acéptalo.
3. Pulsa **Instalar**. Aparecerá el icono **«Corrector»** en el cajón de apps.

> Es una app firmada con un certificado propio (no de Google Play), por eso
> Android avisa de origen desconocido. Es normal para apps fuera de la Play Store.

## Notas

- La app necesita **conexión a internet la primera vez** (carga la PWA). Después
  funciona también sin conexión gracias a su caché.
- Como abre la web publicada, **se actualiza sola** cuando subes cambios a
  GitHub Pages: no hay que reinstalar el APK por cada mejora.
- Permiso de **cámara**: la app lo pedirá al usar la cámara en vivo. La opción
  «Tomar / elegir foto» usa la cámara nativa del móvil.

## Cómo se generó (para regenerarlo)

Proyecto TWA en `apk_build/` (Bubblewrap). Build real en ruta ASCII
`C:\corrector_apk` (el plugin de Android rechaza rutas con caracteres como «Ó»).

```powershell
# 1) Regenerar proyecto desde twa-manifest.json (si cambió)
$env:BUBBLEWRAP_KEYSTORE_PASSWORD="corrector"; $env:BUBBLEWRAP_KEY_PASSWORD="corrector"
bubblewrap update --skipVersionUpgrade

# 2) Compilar (en C:\corrector_apk, copia con ruta ASCII)
$env:JAVA_HOME="C:\Users\Usuario\.bubblewrap\jdk\jdk-17.0.11+9"
.\gradlew.bat assembleRelease --no-daemon --max-workers=1

# 3) Alinear y firmar
$bt="C:\Users\Usuario\.bubblewrap\android_sdk\build-tools\35.0.0"
& "$bt\zipalign.exe" -f -p 4 app\build\outputs\apk\release\app-release-unsigned.apk aligned.apk
& "$bt\apksigner.bat" sign --ks android.keystore --ks-pass pass:corrector --key-pass pass:corrector --out corrector-examenes.apk aligned.apk
```

> Notas de esta máquina: poca RAM libre → se compiló con `minifyEnabled false`
> y `--max-workers=1` para evitar errores de memoria en el *dexing*.
> Keystore: `apk_build/android.keystore` (alias `android`, contraseña `corrector`).
