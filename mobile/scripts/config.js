// SlabCoach iOS (ex-LockerRoom) : ecrit capacitor.config.json a partir de l'adresse de l'app en ligne (variable LR_URL,
// sinon lr_url.txt). L'app iPhone charge l'app web de Render : une mise a jour du site = l'app a jour,
// sans repasser par Apple (sauf changement natif).
const fs = require('fs');
const path = require('path');
const ici = path.join(__dirname, '..');
let url = (process.env.LR_URL || '').trim();
if (!url && fs.existsSync(path.join(ici, 'lr_url.txt'))) url = fs.readFileSync(path.join(ici, 'lr_url.txt'), 'utf8').trim();
if (!/^https:\/\/[a-z0-9.-]+(:\d+)?\/?$/i.test(url)) {
  console.error("LR_URL manquante ou invalide (ex. https://slabcoach.com) : ecris-la dans mobile/lr_url.txt");
  process.exit(1);
}
url = url.replace(/\/$/, '');
const hote = new URL(url).hostname;
const conf = {
  appId: 'com.slabcoach.app',
  appName: 'SlabCoach',
  webDir: 'www',
  server: {
    url,
    errorPath: 'erreur.html',                 // hors ligne : un ecran natif avec « Reessayer », pas une page d'erreur
    allowNavigation: [hote, '*.' + hote.replace(/^www\./, ''), 'appleid.apple.com', '*.ebay.com', '*.ebay.ca', 'signin.ebay.com', 'auth.ebay.com', 'auth.sandbox.ebay.com', 'signin.sandbox.ebay.com']
  },
  ios: {
    contentInset: 'never',
    scheme: 'SlabCoach',
    appendUserAgent: 'LockerRoomiOS/1.0',       // le serveur et l'ecran savent qu'on est dans l'app iPhone
    backgroundColor: '#0B0B0E',
    limitsNavigationsToAppBoundDomains: false
  },
  plugins: {
    SplashScreen: { launchShowDuration: 900, launchAutoHide: true, backgroundColor: '#0B0B0E', showSpinner: false },
    StatusBar: { style: 'DARK', backgroundColor: '#0B0B0E', overlaysWebView: true },
    PushNotifications: { presentationOptions: ['badge', 'sound', 'alert'] }
  }
};
fs.writeFileSync(path.join(ici, 'capacitor.config.json'), JSON.stringify(conf, null, 2));
// 28 oct 2026 : les pages locales (demarrage, erreur) savent ou est l'app en ligne : « Reessayer » y retourne
fs.writeFileSync(path.join(ici, 'www', 'lr_url.js'), 'window.LR_URL = ' + JSON.stringify(url) + ';\n');
console.log('capacitor.config.json -> ' + url);
