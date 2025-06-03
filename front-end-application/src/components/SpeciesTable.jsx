export default function SpeciesTable({ rows = [] }) {
  if (!rows.length) {
    return (
      <p className="p-4 text-center text-gray-500">
        No species in the result set.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto border rounded">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-100 text-left">
          <tr>
            <th className="p-2">Espèce</th>
            <th className="p-2">Famille</th>
            <th className="p-2">Taille</th>
            <th className="p-2">Région</th>
            <th className="p-2 text-right">Images</th>
            <th className="p-2 text-right">Complétude %</th>
            <th className="p-2">Description</th>
          </tr>
        </thead>

        <tbody>
          {rows.map((r) => (
            <tr key={r.species_id} className="border-t">
              <td className="p-2">{r.species_name}</td>
              <td className="p-2">{r.family}</td>
              <td className="p-2">{r.taille || "–"}</td>
              <td className="p-2">{r.region}</td>
              <td className="p-2 text-right">{r.total_images}</td>
              <td className="p-2 text-right">
                {Number(r.completeness_percentage).toFixed(2)} %
              </td>
              <td className="p-2">{r.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
