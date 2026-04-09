import re

with open("frontend/index.html", "r") as f:
    html = f.read()

# Replace block/mining badge strings inside HTML templates
html = html.replace('Block #${d.blockIndex} · Owner: ${user}', 
                    'Algo TxID: <a href="https://lora.algonode.network/testnet/transaction/${d.algoTxId}" target="_blank" style="color:var(--primary)">${d.algoTxId.substring(0,8)}...</a> · Owner: ${user}')

html = html.replace('<div class="mining-badge">⛏ Mined in ${d.miningTime ?? \'?\'}s · ${(d.attempts ?? 0).toLocaleString()} attempts</div>', '')

html = html.replace('`Model "${name}" registered on Block #${d.blockIndex}`', 
                    '`Model "${name}" broadcast to Algorand Testnet!`')

html = html.replace('Block #${d.blockIndex} · Verifier: ${user}', 
                    'Algo TxID: <a href="https://lora.algonode.network/testnet/transaction/${d.algoTxId}" target="_blank" style="color:var(--primary)">${d.algoTxId.substring(0,8)}...</a> · Verifier: ${user}')

html = html.replace('<td>#${v.blockIndex}</td>', 
                    '<td><a href="https://lora.algonode.network/testnet/transaction/${v.algoTxId}" target="_blank">AlgoTx</a></td>')

html = html.replace("if (d.success) { toast('ok', `Version ${d.version} added on Block #${d.blockIndex} · ⛏ ${d.miningTime ?? '?'}s · ${(d.attempts ?? 0).toLocaleString()} attempts`); refreshStats(); }", 
                    "if (d.success) { toast('ok', `Version ${d.version} added to Algorand Testnet`); refreshStats(); }")

html = html.replace("<td>#${v.blockIndex || '—'}</td>", 
                    "<td>${v.algoTxId ? `<a href='https://lora.algonode.network/testnet/transaction/${v.algoTxId}' target='_blank'>AlgoTx</a>` : '—'}</td>")

html = html.replace("<span>Block #${m.blockIndex}</span>", 
                    "<span>Algorand Tx</span>")

html = html.replace("<span>⛓ Block #${m.blockIndex}</span>", 
                    "<span>⛓ Algorand Hosted</span>")

with open("frontend/index.html", "w") as f:
    f.write(html)
