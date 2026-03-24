import {
  Chart,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js'

export default defineNuxtPlugin(() => {
  Chart.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    BarElement,
    ArcElement,
    Filler,
    Tooltip,
    Legend,
  )

  Chart.defaults.color = '#8B95A5'
  Chart.defaults.borderColor = 'rgba(255,255,255,0.06)'
  Chart.defaults.font.family = 'Inter, system-ui, sans-serif'
  Chart.defaults.font.size = 11
  Chart.defaults.plugins.legend.labels.usePointStyle = true
  Chart.defaults.plugins.legend.labels.pointStyle = 'circle'
  Chart.defaults.plugins.legend.labels.boxWidth = 6
  Chart.defaults.plugins.tooltip.backgroundColor = '#1A2540'
  Chart.defaults.plugins.tooltip.borderColor = 'rgba(255,255,255,0.1)'
  Chart.defaults.plugins.tooltip.borderWidth = 1
  Chart.defaults.plugins.tooltip.padding = 10
  Chart.defaults.plugins.tooltip.cornerRadius = 8
  Chart.defaults.elements.point.radius = 0
  Chart.defaults.elements.point.hoverRadius = 4
  Chart.defaults.elements.line.tension = 0.3
})
