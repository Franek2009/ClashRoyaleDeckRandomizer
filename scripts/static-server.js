import {createReadStream, existsSync, statSync} from "node:fs";
import {createServer} from "node:http";
import {extname, join, normalize} from "node:path";

const root = process.cwd();
const port = Number(process.env.PORT || 4173);
const types = {".css": "text/css", ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml", ".ttf": "font/ttf"};

createServer((request, response) => {
    const pathname = decodeURIComponent(new URL(request.url, `http://${request.headers.host}`).pathname);
    const relative = normalize(pathname).replace(/^(\.\.(\/|\\|$))+/, "");
    let file = join(root, relative);
    if (pathname === "/" || (existsSync(file) && statSync(file).isDirectory())) file = join(file, "index.html");
    if (!file.startsWith(root) || !existsSync(file) || !statSync(file).isFile()) {
        response.writeHead(404); response.end("Not found"); return;
    }
    response.writeHead(200, {"Content-Type": `${types[extname(file)] || "application/octet-stream"}; charset=utf-8`, "Cache-Control": "no-store"});
    createReadStream(file).pipe(response);
}).listen(port, "127.0.0.1", () => console.log(`Static server listening on http://127.0.0.1:${port}`));
