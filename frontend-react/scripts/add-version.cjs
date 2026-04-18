const fs = require('fs');
const path = require('path');

const version = process.argv[2] || Date.now().toString();
const indexPath = path.join(__dirname, '..', 'dist', 'index.html');

let html = fs.readFileSync(indexPath, 'utf-8');

html = html.replace(/(src|href)="(\/assets\/[^"]+)"/g, (match, attr, filepath) => {
    const sep = filepath.includes('?') ? '&' : '?';
    return `${attr}="${filepath}${sep}v=${version}"`;
});

fs.writeFileSync(indexPath, html);
console.log(`Added version=${version} to dist/index.html`);
