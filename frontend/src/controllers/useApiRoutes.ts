import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createApiRoute, deleteApiRoute, listApiRoutes, updateApiRoute } from "../services/catalogService";

export const useApiRoutes = () => {
  return useQuery({ queryKey: ["api-routes"], queryFn: listApiRoutes });
};

export const useCreateApiRoute = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createApiRoute,
    onSuccess: () => client.invalidateQueries({ queryKey: ["api-routes"] })
  });
};

export const useUpdateApiRoute = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Record<string, unknown> }) =>
      updateApiRoute(id, payload),
    onSuccess: () => client.invalidateQueries({ queryKey: ["api-routes"] })
  });
};

export const useDeleteApiRoute = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: deleteApiRoute,
    onSuccess: () => client.invalidateQueries({ queryKey: ["api-routes"] })
  });
};
