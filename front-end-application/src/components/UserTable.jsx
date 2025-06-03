import { useEffect, useState } from 'react';
import { getUserList } from '../services/DataService.js';

export default function UserTable() {
  const [users, setUsers] = useState([]);

  useEffect(() => {
    getUserList().then(setUsers);
  }, []);

  return (
    <table className="min-w-full border my-6">
      <thead className="bg-gray-100">
        <tr>
          <th className="p-2 text-left">ID</th>
          <th className="p-2 text-left">Name</th>
          <th className="p-2 text-left">Email</th>
          <th className="p-2 text-left">Role</th>
        </tr>
      </thead>
      <tbody>
        {users.map((u) => (
          <tr key={u.id} className="border-t hover:bg-gray-50">
            <td className="p-2">{u.id}</td>
            <td className="p-2">{u.name}</td>
            <td className="p-2">{u.email}</td>
            <td className="p-2 capitalize">{u.role}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}