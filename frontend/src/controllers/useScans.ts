import { useQuery } from "@tanstack/react-query";
import { getSchema, listScans } from "../services/catalogService";

export const useScans = (connectionId?: number) => {
  return useQuery({
    queryKey: ["scans", connectionId],
    queryFn: () => listScans(connectionId ?? 0),
    enabled: Boolean(connectionId)
  });
};

export const useSchema = (scanId?: number) => {
  return useQuery({
    queryKey: ["schema", scanId],
    queryFn: () => getSchema(scanId ?? 0),
    enabled: Boolean(scanId)
  });
};
