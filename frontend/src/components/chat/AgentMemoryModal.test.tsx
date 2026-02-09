import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, Mock } from 'vitest';
import AgentMemoryModal from './AgentMemoryModal';
import * as useMemoryItemsModule from '../../hooks/useMemoryItems';

// Mock the hook
vi.mock('../../hooks/useMemoryItems');

const mockUseMemoryItems = {
  items: [],
  loading: false,
  error: null,
  hasMore: false,
  fetchItems: vi.fn(),
  createItem: vi.fn(),
  updateStatus: vi.fn(),
  promoteItem: vi.fn(),
  deleteItem: vi.fn(),
  clearCategory: vi.fn(),
};

describe('AgentMemoryModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useMemoryItemsModule.default as Mock).mockReturnValue(mockUseMemoryItems);
  });

  it('renders correctly when open', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    expect(screen.getByText('Student Memory')).toBeInTheDocument();
    expect(screen.getByText('Personal Info')).toBeInTheDocument();
    expect(screen.getByText('Areas to Improve')).toBeInTheDocument();
    expect(screen.getByText('Knowledge Strengths')).toBeInTheDocument();
  });

  it('fetches items on mount when open', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalledWith('personal_info', undefined, true);
  });

  it('changes category when tab is clicked', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    const areasTab = screen.getByText('Areas to Improve');
    fireEvent.click(areasTab);

    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalledWith('area_to_improve', undefined, true);
  });

  it('opens add form when "Add Item" is clicked', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    const addButton = screen.getByText('Add Item');
    fireEvent.click(addButton);

    expect(screen.getByText('Add Memory Item')).toBeInTheDocument();
    expect(screen.getByLabelText(/Key/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Content/i)).toBeInTheDocument();
  });

  it('displays items in cards', () => {
    const mockItems = [
      {
        id: 1,
        key: 'test-key',
        content: 'test-content',
        category: 'personal_info',
        status: 'active',
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    expect(screen.getByText('test-key')).toBeInTheDocument();
    expect(screen.getByText('test-content')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('calls clearCategory when "Clear Category" is clicked and confirmed', () => {
    window.confirm = vi.fn(() => true);
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: [{ id: 1 }], // Ensure button is enabled
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    const clearButton = screen.getByText('Clear Category');
    fireEvent.click(clearButton);

    expect(window.confirm).toHaveBeenCalled();
    expect(mockUseMemoryItems.clearCategory).toHaveBeenCalledWith('personal_info');
  });
});
