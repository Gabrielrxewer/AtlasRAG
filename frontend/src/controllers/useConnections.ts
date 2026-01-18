import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createConnection, deleteConnection, listConnections, scanConnection } from "../services/catalogService";

export const useConnections = () => {
  return useQuery({ queryKey: ["connections"], queryFn: listConnections });
};

export const useCreateConnection = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createConnection,
    onSuccess: () => client.invalidateQueries({ queryKey: ["connections"] })
  });
};

export const useDeleteConnection = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: deleteConnection,
    onSuccess: () => client.invalidateQueries({ queryKey: ["connections"] })
  });
};

export const useScanConnection = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: scanConnection,
    onSuccess: () => client.invalidateQueries({ queryKey: ["scans"] })
  });
};
