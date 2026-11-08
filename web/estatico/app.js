// Interfaz del mostrador: conversación a la izquierda, traza de herramientas a la derecha.
const $ = (id) => document.getElementById(id);
let trazaCompleta = []; // todo lo que pasó en la conversación, para exportar

async function api(ruta, cuerpo) {
  const opciones = cuerpo === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo),
  };
  const r = await fetch(ruta, opciones);
  const datos = await r.json();
  if (!r.ok) throw new Error(datos.detail || r.statusText);
  return datos;
}

function avisar(texto) {
  $("aviso").textContent = texto || "";
  $("aviso").hidden = !texto;
}

function agregarMensaje(texto, clase) {
  const div = document.createElement("div");
  div.className = "msg " + clase;
  div.textContent = texto;
  $("mensajes").appendChild(div);
  div.scrollIntoView();
  return div;
}

function mostrarTraza(turno, pasos) {
  const cont = $("pasos");
  cont.querySelector(".vacio")?.remove();
  const titulo = document.createElement("div");
  titulo.className = "turno";
  titulo.textContent = `Turno ${turno}` + (pasos.length ? "" : ": sin herramientas");
  cont.appendChild(titulo);
  for (const p of pasos) {
    const div = document.createElement("div");
    div.className = "paso";
    div.innerHTML = "<b></b><pre></pre><pre></pre>";
    div.querySelector("b").textContent = p.herramienta;
    div.querySelectorAll("pre")[0].textContent = "argumentos: " + JSON.stringify(p.argumentos, null, 2);
    const res = div.querySelectorAll("pre")[1];
    res.textContent = "resultado: " + JSON.stringify(p.resultado, null, 2);
    if (p.resultado && p.resultado.error) res.classList.add("error");
    cont.appendChild(div);
  }
  cont.lastChild.scrollIntoView();
}

async function nuevaConversacion() {
  await api("/api/sesion", { cliente_id: $("cliente").value });
  $("mensajes").innerHTML = "";
  $("pasos").innerHTML = '<p class="vacio">Aquí aparecerá cada herramienta que use el agente.</p>';
  $("contador").textContent = "";
  trazaCompleta = [];
}

async function cargarClientes() {
  try {
    const clientes = await api("/api/clientes");
    $("cliente").innerHTML = clientes.map((c) => `<option value="${c.id}">${c.id} · ${c.nombre}</option>`).join("");
    avisar("");
    await nuevaConversacion();
  } catch (e) {
    avisar(e.message);
  }
}

$("formulario").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const texto = $("texto").value.trim();
  if (!texto) return;
  $("texto").value = "";
  agregarMensaje(texto, "usuario");
  const espera = agregarMensaje("El agente está pensando…", "agente esperando");
  try {
    const r = await api("/api/mensaje", { texto });
    espera.remove();
    agregarMensaje(r.respuesta, "agente");
    mostrarTraza(r.turnos, r.traza);
    $("contador").textContent = `Turnos: ${r.turnos} · Tokens: ${r.tokens.entrada} entrada, ${r.tokens.salida} salida`;
    trazaCompleta.push({ turno: r.turnos, cliente_id: $("cliente").value, mensaje: texto, respuesta: r.respuesta, herramientas: r.traza });
    avisar("");
  } catch (e) {
    espera.remove();
    avisar(e.message);
  }
});

$("cliente").addEventListener("change", nuevaConversacion);
$("nueva").addEventListener("click", nuevaConversacion);

$("restablecer").addEventListener("click", async () => {
  if (!confirm("¿Restablecer los datos de la tienda a su estado original?")) return;
  await api("/api/restablecer", {});
  await cargarClientes();
});

$("exportar").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(trazaCompleta, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `traza-${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.json`;
  a.click();
});

cargarClientes();
