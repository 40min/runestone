import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, Mock } from 'vitest';
import AgentMemoryModal from './AgentMemoryModal';
import * as useMemoryItemsModule from '../../hooks/useMemoryItems';

// Mock the hook
vi.mock('../../hooks/useMemoryItems');

const mockUpdatePriority = vi.fn().mockResolvedValue(undefined);

const mockUseMemoryItems = {
  items: [],
  loading: false,
  error: null,
  hasMore: false,
  fetchItems: vi.fn(),
  createItem: vi.fn(),
  updateStatus: vi.fn(),
  updatePriority: mockUpdatePriority,
  deleteItem: vi.fn().mockResolvedValue(undefined),
  clearCategory: vi.fn().mockResolvedValue(undefined),
};

describe('AgentMemoryModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useMemoryItemsModule.default as Mock).mockReturnValue(mockUseMemoryItems);
  });

  it('renders correctly when open', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    expect(screen.getByText("Teacher's Memory")).toBeInTheDocument();
    expect(screen.getByText('0 items')).toBeInTheDocument();
    expect(screen.getByText('Personal Info')).toBeInTheDocument();
    expect(screen.getByText('Areas to Improve')).toBeInTheDocument();
    expect(screen.queryByText('Knowledge Strengths')).not.toBeInTheDocument();
  });

  it('fetches items on mount when open', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalledWith('personal_info', undefined, true, 'updated_at', 'desc');
  });

  it('changes category when tab is clicked', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    const areasTab = screen.getByText('Areas to Improve');
    fireEvent.click(areasTab);

    expect(mockUseMemoryItems.fetchItems).toHaveBeenCalledWith('area_to_improve', undefined, true, 'updated_at', 'desc');
  });

  it('keeps updated_at desc default on Areas to Improve tab', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByText('Areas to Improve'));
    expect(mockUseMemoryItems.fetchItems).toHaveBeenLastCalledWith('area_to_improve', undefined, true, 'updated_at', 'desc');
  });

  it('allows selecting Priority + Ascending sort on Areas to Improve tab', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByText('Areas to Improve'));

    const sortBySelect = document.querySelector('[aria-labelledby="sort-by-label"]') as HTMLElement;
    fireEvent.mouseDown(sortBySelect);
    fireEvent.click(screen.getByText('Priority'));

    const directionSelect = document.querySelector('[aria-labelledby="sort-direction-label"]') as HTMLElement;
    fireEvent.mouseDown(directionSelect);
    fireEvent.click(screen.getByText('Ascending'));

    expect(mockUseMemoryItems.fetchItems).toHaveBeenLastCalledWith('area_to_improve', undefined, true, 'priority', 'asc');
  });

  it('resets sort to updated_at desc and hides Priority option when leaving Areas to Improve', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByText('Areas to Improve'));

    const sortBySelect = document.querySelector('[aria-labelledby="sort-by-label"]') as HTMLElement;
    fireEvent.mouseDown(sortBySelect);
    fireEvent.click(screen.getByText('Priority'));

    fireEvent.click(screen.getByText('Personal Info'));
    expect(mockUseMemoryItems.fetchItems).toHaveBeenLastCalledWith('personal_info', undefined, true, 'updated_at', 'desc');

    const personalSortBySelect = document.querySelector('[aria-labelledby="sort-by-label"]') as HTMLElement;
    fireEvent.mouseDown(personalSortBySelect);
    expect(screen.queryByText('Priority')).not.toBeInTheDocument();
  });

  it('opens add form when "Add Item" is clicked', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    const addButton = screen.getByText('Add Item');
    fireEvent.click(addButton);

    expect(screen.getByText('Add Memory Item')).toBeInTheDocument();
    expect(screen.getByLabelText(/Key/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Content/i)).toBeInTheDocument();
  });

  it('shows category-specific status options in add form for area_to_improve', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByText('Areas to Improve'));
    fireEvent.click(screen.getByText('Add Item'));

    const formStatusSelect = document.querySelector(
      '[aria-labelledby="form-status-label"]'
    ) as HTMLElement;
    fireEvent.mouseDown(formStatusSelect);
    expect(screen.getByText('Struggling')).toBeInTheDocument();
    expect(screen.getByText('Improving')).toBeInTheDocument();
    expect(screen.getByText('Mastered')).toBeInTheDocument();
    expect(screen.queryByText('Outdated')).not.toBeInTheDocument();
  });

  it('does not offer Active status for area_to_improve in add form', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByText('Areas to Improve'));
    fireEvent.click(screen.getByText('Add Item'));

    const formStatusSelect = document.querySelector(
      '[aria-labelledby="form-status-label"]'
    ) as HTMLElement;
    fireEvent.mouseDown(formStatusSelect);
    expect(screen.queryByText('Active')).not.toBeInTheDocument();
  });

  it('displays items in cards', () => {
    const mockItems = [
      {
        id: 1,
        key: 'test-key',
        content: 'test-content',
        category: 'personal_info',
        status: 'active',
        priority: null,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    expect(screen.getAllByText('test-key').length).toBeGreaterThan(0);
    expect(screen.getByText('test-content')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('1 item')).toBeInTheDocument();
  });

  it('shows category helper text for areas to improve', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByText('Areas to Improve'));

    expect(
      screen.getByText("These are areas where you've shown difficulty. Focus on them to improve faster!")
    ).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Priority badge tests
  // ---------------------------------------------------------------------------

  it('shows priority badge for area_to_improve item with priority set', () => {
    const mockItems = [
      {
        id: 1,
        key: 'verb-tense',
        content: 'Struggles with verb tense',
        category: 'area_to_improve',
        status: 'struggling',
        priority: 2,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    expect(screen.getByLabelText('Priority badge')).toBeInTheDocument();
    expect(screen.getByLabelText('Priority badge')).toHaveTextContent('P2');
  });

  it('shows P– badge for area_to_improve item without priority', () => {
    const mockItems = [
      {
        id: 1,
        key: 'pronunciation',
        content: 'Pronunciation issues',
        category: 'area_to_improve',
        status: 'struggling',
        priority: null,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    expect(screen.getByLabelText('Priority badge')).toHaveTextContent('P–');
  });

  it('does not show priority badge for personal_info items', () => {
    const mockItems = [
      {
        id: 1,
        key: 'name',
        content: 'Alice',
        category: 'personal_info',
        status: 'active',
        priority: null,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);
    expect(screen.queryByLabelText('Priority badge')).not.toBeInTheDocument();
  });

  it('clicking priority badge shows inline priority selector', () => {
    const mockItems = [
      {
        id: 1,
        key: 'verb-tense',
        content: 'Struggles with verb tense',
        category: 'area_to_improve',
        status: 'struggling',
        priority: 2,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByLabelText('Priority badge'));
    expect(screen.getByLabelText('Priority selector')).toBeInTheDocument();
  });

  it('shows priority field in add form when category is area_to_improve', async () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    // Switch to area_to_improve tab
    fireEvent.click(screen.getByText('Areas to Improve'));
    fireEvent.click(screen.getByText('Add Item'));

    expect(screen.getByLabelText(/Priority/i)).toBeInTheDocument();
  });

  it('does not show priority field in add form for personal_info', () => {
    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    // personal_info is the default tab
    fireEvent.click(screen.getByText('Add Item'));

    expect(screen.queryByLabelText(/Priority/i)).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Existing tests
  // ---------------------------------------------------------------------------

  it('shows inline clear confirmation and calls clearCategory on confirm', async () => {
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: [{ id: 1 }], // Ensure button is enabled
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByText('Clear Category'));
    expect(screen.getByText('Confirm Clear')).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByText('Confirm Clear'));
    });
    expect(mockUseMemoryItems.clearCategory).toHaveBeenCalledWith('personal_info');
  });

  it('cancels inline clear confirmation', () => {
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: [{ id: 1 }],
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByText('Clear Category'));
    fireEvent.click(screen.getByText('Cancel'));

    expect(screen.getByText('Clear Category')).toBeInTheDocument();
    expect(screen.queryByText('Confirm Clear')).not.toBeInTheDocument();
  });

  it('shows inline delete confirmation and cancels', () => {
    const mockItems = [
      {
        id: 1,
        key: 'test-key',
        content: 'test-content',
        category: 'personal_info',
        status: 'active',
        priority: null,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByLabelText('Delete item'));
    expect(screen.getByLabelText('Confirm delete')).toBeInTheDocument();
    expect(screen.getByLabelText('Cancel delete')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Cancel delete'));
    expect(screen.getByLabelText('Delete item')).toBeInTheDocument();
  });

  it('confirms delete and calls deleteItem', async () => {
    const mockItems = [
      {
        id: 1,
        key: 'test-key',
        content: 'test-content',
        category: 'personal_info',
        status: 'active',
        priority: null,
        updated_at: new Date().toISOString(),
      }
    ];
    (useMemoryItemsModule.default as Mock).mockReturnValue({
      ...mockUseMemoryItems,
      items: mockItems,
    });

    render(<AgentMemoryModal open={true} onClose={() => {}} />);

    fireEvent.click(screen.getByLabelText('Delete item'));
    await act(async () => {
      fireEvent.click(screen.getByLabelText('Confirm delete'));
    });

    expect(mockUseMemoryItems.deleteItem).toHaveBeenCalledWith(1);
  });
});
