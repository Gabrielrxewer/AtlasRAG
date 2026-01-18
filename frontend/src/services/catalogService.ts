import api from "./api";
import { ApiRoute, Connection, RagAnswer, Sample, Scan, TableSchema } from "../models/types";

export const listConnections = async (): Promise<Connection[]> => {
  const { data } = await api.get("/connections");
  return data;
};

export const createConnection = async (payload: Record<string, unknown>) => {
  const { data } = await api.post("/connections", payload);
  return data;
};

export const deleteConnection = async (id: number) => {
  const { data } = await api.delete(`/connections/${id}`);
  return data;
};

export const scanConnection = async (id: number): Promise<Scan> => {
  const { data } = await api.post(`/connections/${id}/scan`);
  return data;
};

export const listScans = async (connectionId: number): Promise<Scan[]> => {
  const { data } = await api.get(`/connections/${connectionId}/scans`);
  return data;
};

export const getSchema = async (scanId: number): Promise<TableSchema[]> => {
  const { data } = await api.get(`/scans/${scanId}/schema`);
  return data;
};

export const getSamples = async (tableId: number): Promise<Sample[]> => {
  const { data } = await api.get(`/tables/${tableId}/samples`);
  return data;
};

export const updateTableAnnotations = async (tableId: number, payload: Record<string, unknown>) => {
  const { data } = await api.put(`/tables/${tableId}/annotations`, payload);
  return data;
};

export const updateColumnAnnotations = async (columnId: number, payload: Record<string, unknown>) => {
  const { data } = await api.put(`/columns/${columnId}/annotations`, payload);
  return data;
};

export const listApiRoutes = async (): Promise<ApiRoute[]> => {
  const { data } = await api.get("/api-routes");
  return data;
};

export const createApiRoute = async (payload: Record<string, unknown>): Promise<ApiRoute> => {
  const { data } = await api.post("/api-routes", payload);
  return data;
};

export const updateApiRoute = async (id: number, payload: Record<string, unknown>) => {
  const { data } = await api.put(`/api-routes/${id}`, payload);
  return data;
};

export const deleteApiRoute = async (id: number) => {
  const { data } = await api.delete(`/api-routes/${id}`);
  return data;
};

export const askRag = async (question: string): Promise<RagAnswer> => {
  const { data } = await api.post("/rag/ask", { question });
  return data;
};

export const reindexRag = async (payload: Record<string, unknown>) => {
  const { data } = await api.post("/rag/index", payload);
  return data;
};
