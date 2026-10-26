const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const mqtt = path.dirname(require.resolve('mqtt/package.json'));
fs.mkdirSync(path.join(root, 'web/vendor'), {recursive:true});
fs.copyFileSync(path.join(mqtt, 'dist/mqtt.min.js'), path.join(root, 'web/vendor/mqtt.min.js'));
fs.copyFileSync(path.join(mqtt, 'LICENSE.md'), path.join(root, 'web/vendor/MQTT-LICENSE.md'));
console.log('Vendored MQTT.js 5.16.1 + MIT license. No CDN needed at runtime.');
