-- autocmds.lua — additions to LazyVim's autocmds.

local aug = vim.api.nvim_create_augroup("user_autocmds", { clear = true })

-- Trim trailing whitespace on save (but not for filetypes where it's significant).
vim.api.nvim_create_autocmd("BufWritePre", {
  group = aug,
  callback = function()
    local skip = { markdown = true, diff = true, patch = true }
    if skip[vim.bo.filetype] then return end
    local save = vim.fn.winsaveview()
    vim.cmd([[silent! %s/\s\+$//e]])
    vim.fn.winrestview(save)
  end,
})

-- Restore last cursor position.
vim.api.nvim_create_autocmd("BufReadPost", {
  group = aug,
  callback = function()
    local mark = vim.api.nvim_buf_get_mark(0, '"')
    local lcount = vim.api.nvim_buf_line_count(0)
    if mark[1] > 0 and mark[1] <= lcount then
      pcall(vim.api.nvim_win_set_cursor, 0, mark)
    end
  end,
})
