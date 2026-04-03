// Plugin personalizado para mostrar un valor en el centro de la gráfica doughnut
const centerValuePlugin = {
    id: "centerValuePlugin",

    // Se ejecuta después de que la gráfica se dibuja
    afterDraw(chart) {

        // Obtener el dataset de la gráfica
        const dataset = chart.data.datasets[0];

        // Calcular la suma total de los valores
        const total = dataset.data.reduce((sum, value) => sum + value, 0);

        // Obtener el valor más alto del dataset
        const top = Math.max(...dataset.data);

        // Calcular el porcentaje que representa el valor más alto
        const percent = Math.round((top / total) * 100);

        // Obtener el punto central de la gráfica
        const point = chart.getDatasetMeta(0).data[0];
        const x = point.x;
        const y = point.y;

        // Obtener el contexto del canvas
        const ctx = chart.ctx;

        ctx.save();

        // Configuración del texto principal (porcentaje)
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#162033";
        ctx.font = "700 26px Segoe UI";

        // Mostrar el porcentaje en el centro
        ctx.fillText(`${percent}%`, x, y - 6);

        // Configuración del texto secundario
        ctx.fillStyle = "#61708c";
        ctx.font = "500 12px Segoe UI";

        // Texto descriptivo debajo del porcentaje
        ctx.fillText("Top segment", x, y + 16);

        ctx.restore();
    }
};


// Opciones generales que comparten todas las gráficas
const commonOptions = {

    // Hace que la gráfica se adapte al tamaño del contenedor
    responsive: true,

    // Evita mantener una relación de aspecto fija
    maintainAspectRatio: false,

    // Tamaño del hueco interno de la gráfica doughnut
    cutout: "74%",

    // Configuración de animación al cargar la gráfica
    animation: {
        duration: 1000
    },

    plugins: {

        // Configuración de la leyenda
        legend: {
            position: "bottom", // posición de la leyenda
            labels: {
                boxWidth: 12, // tamaño del cuadro de color
                color: "#223049", // color del texto
                font: {
                    size: 11
                }
            }
        },

        // Configuración del tooltip (mensaje al pasar el mouse)
        tooltip: {
            backgroundColor: "#101522",
            titleColor: "#ffffff",
            bodyColor: "#dce6ff"
        }
    }
};


// Primera grafica (Devices)
const devicesChart = document.getElementById("grafica1");
const onlineCount = Number(devicesChart.dataset.online || 0);
const offlineCount = Number(devicesChart.dataset.offline || 0);
const deviceChartData = onlineCount === 0 && offlineCount === 0 ? [1, 0] : [onlineCount, offlineCount];

new Chart(devicesChart, {

    // Tipo de gráfica
    type: "doughnut",

    data: {

        // Etiquetas de los datos
        labels: ["Online", "Offline"],

        datasets: [{
            data: deviceChartData, // valores de los datos

            // Colores de cada segmento
            backgroundColor: ["#2f6fed", "#7db0ff"],

            // Color del borde de cada segmento
            borderColor: "#ffffff",

            // Grosor del borde
            borderWidth: 3,

            // Bordes redondeados
            borderRadius: 12,

            // Animación al pasar el mouse
            hoverOffset: 6
        }]
    },

    options: commonOptions,

    // Uso del plugin personalizado
    plugins: [centerValuePlugin]
});


// Segunda gráfica (Servers)
const serversChart = document.getElementById("grafica2");
const serverOnlineCount = Number(serversChart.dataset.online || 0);
const serverOfflineCount = Number(serversChart.dataset.offline || 0);
const serverChartData = serverOnlineCount === 0 && serverOfflineCount === 0 ? [1, 0] : [serverOnlineCount, serverOfflineCount];

new Chart(serversChart, {
    type: "doughnut",

    data: {
        labels: ["Online", "Offline"],

        datasets: [{
            data: serverChartData,
            backgroundColor: ["#22b07d", "#77dfbc"],
            borderColor: "#ffffff",
            borderWidth: 3,
            borderRadius: 12,
            hoverOffset: 6
        }]
    },

    options: commonOptions,
    plugins: [centerValuePlugin]
});


// Tercera gráfica (NFV)
const nfvChart = document.getElementById("grafica3");
const routerCount = Number(nfvChart.dataset.router || 0);
const switchCount = Number(nfvChart.dataset.switch || 0);
const nfvChartData = routerCount === 0 && switchCount === 0 ? [1, 0] : [routerCount, switchCount];

new Chart(nfvChart, {
    type: "doughnut",

    data: {
        labels: ["Routers", "Switches"],

        datasets: [{
            data: nfvChartData,
            backgroundColor: ["#f4a62a", "#ffd789"],
            borderColor: "#ffffff",
            borderWidth: 3,
            borderRadius: 12,
            hoverOffset: 6
        }]
    },

    options: commonOptions,
    plugins: [centerValuePlugin]
});
