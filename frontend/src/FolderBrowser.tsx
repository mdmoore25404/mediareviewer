import { type ReactElement, useCallback, useEffect, useState } from "react";

import { fetchFolders } from "./api/client";
import type { FolderInfo } from "./api/types";

interface FolderBrowserProps {
  /** Root paths the user has already configured; browses are anchored within them. */
  knownPaths: string[];
  /** Hidden picker paths from server config — filter from top-level navigation. */
  hiddenPaths: string[];
  /** Called when the user selects a folder to use as the review root. */
  onSelectFolder: (path: string) => void;
  /** Called when the user dismisses the browser without selecting. */
  onClose: () => void;
}

interface FolderNode {
  info: FolderInfo;
  children: FolderNode[] | null; // null = not loaded, [] = loaded empty
  isLoading: boolean;
  isExpanded: boolean;
  error: string | null;
}

function buildRootNodes(knownPaths: string[]): FolderNode[] {
  return knownPaths.map((path) => ({
    info: {
      path,
      name: path,
      has_children: true,
    },
    children: null,
    isLoading: false,
    isExpanded: false,
    error: null,
  }));
}

function updateNodeByPath(
  nodes: FolderNode[],
  targetPath: string,
  updater: (node: FolderNode) => FolderNode,
): FolderNode[] {
  return nodes.map((node) => {
    if (node.info.path === targetPath) {
      return updater(node);
    }
    if (node.children) {
      return {
        ...node,
        children: updateNodeByPath(node.children, targetPath, updater),
      };
    }
    return node;
  });
}

interface FolderNodeRowProps {
  node: FolderNode;
  depth: number;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
}

function FolderNodeRow({ node, depth, onToggle, onSelect }: FolderNodeRowProps): ReactElement {
  const indent = depth * 1.25;

  return (
    <>
      <div
        className="folder-browser-row d-flex align-items-center gap-2 py-1 px-2 rounded"
        style={{ paddingLeft: `${indent + 0.5}rem` }}
      >
        <button
          type="button"
          className="btn btn-link p-0 folder-browser-expand-btn"
          aria-label={node.isExpanded ? `Collapse ${node.info.name}` : `Expand ${node.info.name}`}
          onClick={() => {
            onToggle(node.info.path);
          }}
          disabled={!node.info.has_children || node.isLoading}
        >
          {node.isLoading ? (
            <i className="fa-solid fa-circle-notch fa-spin" aria-hidden="true" />
          ) : node.info.has_children ? (
            <i
              className={node.isExpanded ? "fa-solid fa-chevron-down" : "fa-solid fa-chevron-right"}
              aria-hidden="true"
            />
          ) : (
            <i className="fa-solid fa-minus text-secondary" aria-hidden="true" />
          )}
        </button>
        <i className="fa-regular fa-folder text-warning" aria-hidden="true" />
        <button
          type="button"
          className="btn btn-link p-0 text-start text-truncate folder-browser-name-btn"
          title={node.info.path}
          onClick={() => {
            onSelect(node.info.path);
          }}
        >
          {node.info.name}
        </button>
      </div>

      {node.error && (
        <div
          className="small text-danger ps-3"
          style={{ paddingLeft: `${indent + 2.5}rem` }}
        >
          {node.error}
        </div>
      )}

      {node.isExpanded && node.children?.length === 0 && !node.isLoading && (
        <div
          className="small text-secondary py-1"
          style={{ paddingLeft: `${indent + 2.5}rem` }}
        >
          No subfolders
        </div>
      )}

      {node.isExpanded &&
        node.children?.map((child) => (
          <FolderNodeRow
            key={child.info.path}
            node={child}
            depth={depth + 1}
            onToggle={onToggle}
            onSelect={onSelect}
          />
        ))}
    </>
  );
}

export function FolderBrowser({
  knownPaths,
  onSelectFolder,
  onClose,
}: FolderBrowserProps): ReactElement {
  const [nodes, setNodes] = useState<FolderNode[]>(() => buildRootNodes(knownPaths));

  useEffect(() => {
    setNodes(buildRootNodes(knownPaths));
  }, [knownPaths]);

  const handleToggle = useCallback(
    (path: string) => {
      setNodes((prev) => {
        const target = findNode(prev, path);
        if (!target) return prev;

        if (target.isExpanded) {
          // Collapse
          return updateNodeByPath(prev, path, (n) => ({ ...n, isExpanded: false }));
        }

        if (target.children !== null) {
          // Already loaded — just expand
          return updateNodeByPath(prev, path, (n) => ({ ...n, isExpanded: true }));
        }

        // Need to load children
        const updated = updateNodeByPath(prev, path, (n) => ({
          ...n,
          isLoading: true,
          isExpanded: true,
          error: null,
        }));

        void fetchFolders(path, new AbortController().signal)
          .then((result) => {
            setNodes((current) =>
              updateNodeByPath(current, path, (n) => ({
                ...n,
                isLoading: false,
                children: result.folders.map((folder) => ({
                  info: folder,
                  children: null,
                  isLoading: false,
                  isExpanded: false,
                  error: null,
                })),
              })),
            );
          })
          .catch((error: unknown) => {
            const message = error instanceof Error ? error.message : "Failed to load subfolders.";
            setNodes((current) =>
              updateNodeByPath(current, path, (n) => ({
                ...n,
                isLoading: false,
                isExpanded: false,
                error: message,
              })),
            );
          });

        return updated;
      });
    },
    [],
  );

  const handleSelect = useCallback(
    (path: string) => {
      onSelectFolder(path);
      onClose();
    },
    [onSelectFolder, onClose],
  );

  return (
    <div className="folder-browser" role="dialog" aria-modal="true" aria-label="Browse folders">
      <div className="folder-browser-header d-flex justify-content-between align-items-center px-3 py-2 border-bottom">
        <span className="fw-semibold">
          <i className="fa-solid fa-folder-tree me-2" aria-hidden="true" />
          Browse folders
        </span>
        <button
          type="button"
          className="btn-close"
          aria-label="Close folder browser"
          onClick={onClose}
        />
      </div>
      <div className="folder-browser-body p-2 overflow-auto">
        {nodes.length === 0 ? (
          <p className="small text-secondary p-2 mb-0">
            No review paths configured. Add one above.
          </p>
        ) : (
          nodes.map((node) => (
            <FolderNodeRow
              key={node.info.path}
              node={node}
              depth={0}
              onToggle={handleToggle}
              onSelect={handleSelect}
            />
          ))
        )}
      </div>
    </div>
  );
}

function findNode(nodes: FolderNode[], path: string): FolderNode | null {
  for (const node of nodes) {
    if (node.info.path === path) return node;
    if (node.children) {
      const found = findNode(node.children, path);
      if (found) return found;
    }
  }
  return null;
}
