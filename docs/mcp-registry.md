# Publishing the MCP server to the official MCP Registry

`server.json` (repo root) describes the remote MCP server at `https://voicedex.dev/mcp` for
[registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io). The name
`io.github.chandradot99/voicedex` is owned through GitHub login (no keys to keep).

```bash
brew install mcp-publisher          # or see github.com/modelcontextprotocol/registry for other installs
mcp-publisher login github          # opens github.com/login/device; approve as chandradot99
mcp-publisher publish               # reads ./server.json
```

Check it: `curl "https://registry.modelcontextprotocol.io/v0/servers?search=io.github.chandradot99/voicedex"`.

To update the listing (new description, icon, URL), bump `version` in `server.json` and publish again;
a version can only be published once. The registry doesn't track tool changes: tools are discovered
live from `/mcp`, so tool updates need no new publish.
