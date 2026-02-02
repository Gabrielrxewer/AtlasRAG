// Hooks para gerenciamento de agentes.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createAgent,
  listAgentMessages,
  listAgents,
  sendAgentMessage
} from "../services/catalogService";

export const useAgents = () => {
  // Lista agentes cadastrados.
  return useQuery({ queryKey: ["agents"], queryFn: listAgents });
};

export const useCreateAgent = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createAgent,
    onSuccess: () => client.invalidateQueries({ queryKey: ["agents"] })
  });
};

export const useAgentMessages = (agentId?: number) => {
  return useQuery({
    queryKey: ["agent-messages", agentId],
    queryFn: () => listAgentMessages(agentId ?? 0),
    enabled: !!agentId
  });
};

export const useSendAgentMessage = (agentId?: number) => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      sendAgentMessage(agentId ?? 0, payload),
    onSuccess: () => client.invalidateQueries({ queryKey: ["agent-messages", agentId] })
  });
};
