import tkinter as tk

root = tk.Tk()
root.geometry("200x300")

b1 = tk.Button(root, text="Exit (Bottom)", bg="red")
b1.pack(side=tk.BOTTOM, fill=tk.X)

f1 = tk.Frame(root, bg="blue", height=50)
f1.pack(side=tk.BOTTOM, fill=tk.X)

spacer = tk.Frame(root, bg="green")
spacer.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# Simulate forget and repack
# root.update()
# f1.pack_forget()
# We want it to be above Exit, meaning it should be packed after Exit in the bottom stack
# f1.pack(side=tk.BOTTOM, fill=tk.X, after=b1)

root.after(1000, lambda: root.destroy())
root.mainloop()

print("OK")
