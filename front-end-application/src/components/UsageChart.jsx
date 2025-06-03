import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend);

export default function UsageChart({ data }) {
  const chartData = {
    labels: data.labels,
    datasets: [
      {
        label: 'Usage',
        data: data.values,
        fill: false,
        tension: 0.3,
      },
    ],
  };
  return <Line data={chartData} />;
}