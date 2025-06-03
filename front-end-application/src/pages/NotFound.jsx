import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-screen text-center">
      <h1 className="text-4xl font-bold mb-4">404 – Not Found</h1>
      <Link to="/login" className="text-blue-600 underline">
        Go to Login
      </Link>
    </div>
  );
}