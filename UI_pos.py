import Tkinter as tk
import threading
import time
import matplotlib
matplotlib.use("TkAgg")
matplotlib.rcParams.update({
    'font.family': 'Helvetica',
    'font.weight': 'bold',
    'font.size': 13
})
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

def init_AFE4300():
    # Initialize the device
    GUI_Module = __import__('Device_GUI')
    GUI = GUI_Module.Device_GUI("AFE4300 Device GUI")
    GUI.write_register("AFE4300","DEVICE_CONTROL1",0x6006)
    GUI.write_register("AFE4300","DEVICE_CONTROL2",0x0)
    GUI.write_register("AFE4300","ADC_CONTROL_REGISTER1",0x4140)
    GUI.write_register("AFE4300","ADC_CONTROL_REGISTER2",0x63)
    GUI.write_register("AFE4300","ISW_MUX",0x1020)
    GUI.write_register("AFE4300","IQ_MODE_ENABLE",0x0)
    GUI.write_register("AFE4300","BCM_DAC_FREQ", 0x08)
    return GUI

measurement_running = False
measurement_data = []
data_lock = threading.Lock()
ratio_ylim_selector = 1

def measure_loop():
    global measurement_running, GUI, f
    deley_time = 0.15
    while measurement_running:
        cur_time = time.time()
        # Measure data_ch23
        GUI.write_register("AFE4300", "VSENSE_MUX", 0x1020)
        time.sleep(deley_time)
        data_ch23 = GUI.read_register("AFE4300", "ADC_DATA_RESULT")
        if data_ch23 >= 32768:
            data_ch23 -= 65536
        data_ch23 = data_ch23 * (1.7 / 32768.0) * 1000
        # Measure data_ch34
        GUI.write_register("AFE4300", "VSENSE_MUX", 0x2040)
        time.sleep(deley_time)
        data_ch34 = GUI.read_register("AFE4300", "ADC_DATA_RESULT")
        if data_ch34 >= 32768:
            data_ch34 -= 65536
        data_ch34 = data_ch34 * (1.7 / 32768.0) * 1000
        # Measure data_ch24
        GUI.write_register("AFE4300", "VSENSE_MUX", 0x1040)
        time.sleep(deley_time)
        data_ch24 = GUI.read_register("AFE4300", "ADC_DATA_RESULT")
        if data_ch24 >= 32768:
            data_ch24 -= 65536
        data_ch24 = data_ch24 * (1.7 / 32768.0) * 1000
        # Calculate ratio and error
        ratio = float(data_ch23 - data_ch34) / float(data_ch23 + data_ch34) if (data_ch23 + data_ch34) != 0 else 0
        error = abs(1 - (data_ch23 + data_ch34) / float(data_ch24)) if data_ch24 != 0 else 0
        
        # Define ANSI color codes
        RED = "\033[31m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        BLUE = "\033[34m"
        MAGENTA = "\033[35m"
        RESET = "\033[0m"
        
        print("Raw {}A: {:.2f}{} / {}B: {:.2f}{} / {}A+B: {:.2f}{} _ Result {}ratio: {:.2f}{} / {}error: {:.3f}{}".format(
              MAGENTA, data_ch23, RESET,
              YELLOW, data_ch34, RESET,
              BLUE, data_ch24, RESET,
              GREEN, ratio, RESET,
              RED, error, RESET))
        f.write("%.3f,%.3f,%.3f,%.3f,%.3f\n" % (data_ch23, data_ch34, data_ch24, ratio, error))
        f.flush()
        with data_lock:
            measurement_data.append( (cur_time, data_ch23, data_ch34, data_ch24, ratio, error) )
        # FPS = 1/(time.time() - cur_time)
        # print(FPS)

def start_measurement():
    global measurement_running, GUI, f
    if not measurement_running:
        measurement_running = True
        GUI = init_AFE4300()
        filename = time.strftime("PICC_%d%m%y_%H%M%S.csv", time.gmtime())
        f = open(filename, 'w')
        f.write("2-3,3-4,2-4,ratio,error\n")
        t = threading.Thread(target=measure_loop)
        t.setDaemon(True)
        t.start()
        # Schedule update_gui when measurement starts
        root.after(500, update_gui)

def stop_measurement():
    global measurement_running
    measurement_running = False

def update_gui():
    with data_lock:
        if measurement_data:
            latest = measurement_data[-1]
        else:
            latest = (0,0,0,0,0,0)
        cur_time = time.time()
        times, d23, d34, d24, ratios, errors = [], [], [], [], [], []
        for rec in measurement_data:
            if cur_time - rec[0] <= 60:
                times.append(rec[0] - measurement_data[0][0])
                d23.append(rec[1])
                d34.append(rec[2])
                d24.append(rec[3])
                ratios.append(rec[4])
                errors.append(rec[5])
    # Left plot changes
    line_width = 2
    ax_left.cla()
    ax_left.set_facecolor('#222222')
    ax_left.tick_params(axis='both', colors='white', labelsize=10)
    ax_left.plot(times, d23, label="A", linewidth=line_width)
    ax_left.plot(times, d34, label="B", linewidth=line_width)
    ax_left.plot(times, d24, label="A+B", linewidth=line_width)
    leg = ax_left.legend(loc='upper left', facecolor='#222222', edgecolor='#222222')
    for text in leg.get_texts():
        text.set_color("white")
    ax_left.set_title("Raw Data", color='white')
    y_max = max(d23 + d34 + d24) if (d23 + d34 + d24) else 1
    ax_left.set_ylim(0, y_max*1.1)
    ax_left.set_xticks([])
    ax_left.yaxis.grid(True, color='white', linestyle='-', alpha=0.5)  # added y grid
    canvas_left.draw()
    

    # Top plot (Ratio)
    ax_top.cla()
    ax_top.set_facecolor('#222222')
    ax_top.tick_params(axis='both', colors='white', labelsize=10)
    ax_top.plot(times, ratios, label="ratio", color="green", linewidth=line_width)
    ax_top.set_title("Position", color='white')
    ax_top.set_xlim(left=max(0, (times[-1]-60)) if times else 0, right=times[-1] if times else 60)
    ax_top.set_ylim(-ratio_ylim_selector-0.1, ratio_ylim_selector+0.1)
    ax_top.set_xticks([])
    ax_top.set_yticks([-ratio_ylim_selector, 0, ratio_ylim_selector])
    ax_top.set_yticklabels(['A', '0', 'B'])
    ax_top.yaxis.grid(True, color='white', linestyle='-', alpha=0.5)  # added y grid
    canvas_right.draw()
    
    ax_bottom.cla()
    ax_bottom.set_facecolor('#222222')
    ax_bottom.tick_params(axis='both', colors='white', labelsize=10)
    ax_bottom.plot(times, [e * 100 for e in errors], label="error", color="red", linewidth=line_width)
    ax_bottom.set_title("Error (%)", color='white')
    ax_bottom.set_xlim(left=max(0, (times[-1]-60)) if times else 0, right=times[-1] if times else 60)
    ax_bottom.set_ylim(0, 100)
    ax_bottom.set_xticks([])
    ax_bottom.set_yticks([0, 50, 100])
    ax_bottom.yaxis.grid(True, color='white', linestyle='-', alpha=0.5)
    canvas_right.draw()
    
    # Continue updating only if measurement is still running
    if measurement_running:
        root.after(500, update_gui)

# Create main window with black theme
root = tk.Tk()
root.configure(bg='black')
root.title("PICC Detector")
# Set default Tkinter font to Helvetica Bold
root.option_add("*Font", "Helvetica 14 bold")

# Removed table_var and its label
frame_mid = tk.Frame(root, bg='black')
frame_mid.pack(fill=tk.BOTH, expand=True)

fig_left = Figure(figsize=(5,4), facecolor='black')
ax_left = fig_left.add_subplot(111)
canvas_left = FigureCanvasTkAgg(fig_left, master=frame_mid)
canvas_left.get_tk_widget().configure(bg='black')
canvas_left.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

# Modification: Adjust fig_right background and spacing between subplots
fig_right = Figure(figsize=(5,4), facecolor='black')  # changed from 'black'
fig_right.subplots_adjust(hspace=0.5)  # increased spacing between ratio and error plots
ax_top = fig_right.add_subplot(211)
ax_bottom = fig_right.add_subplot(212)
canvas_right = FigureCanvasTkAgg(fig_right, master=frame_mid)
canvas_right.get_tk_widget().configure(bg='black')
canvas_right.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Button changes
frame_bottom = tk.Frame(root, bg='black')
frame_bottom.pack(side=tk.BOTTOM, fill=tk.X)
stop_btn = tk.Button(frame_bottom,
                     text="Stop",
                     command=stop_measurement,
                     bg='gray',
                     fg='black',
                     width=10,
                     height=1,
                     font=('Helvetica', 14, 'bold'))

start_btn = tk.Button(frame_bottom,
                      text="Start",
                      command=start_measurement,
                      bg='gray',
                      fg='black',
                      width=10,
                      height=1,
                      font=('Helvetica', 14, 'bold'))

stop_btn.pack(side=tk.RIGHT, padx=50, pady=20)
start_btn.pack(side=tk.RIGHT, padx=0, pady=20)

# Place the ratio input on the top-right of the right canvas
ratio_entry = tk.Entry(root, font=('Helvetica', 14, 'bold'), width=5)
ratio_entry.insert(0, "1")
ratio_entry.bind("<Return>", lambda event: update_ratio_ylim())
ratio_entry.place(in_=canvas_right.get_tk_widget(), relx=0.78, rely=0.05, x=0, y=0, anchor="nw")

def update_ratio_ylim():
    global ratio_ylim_selector
    try:
        ratio_ylim_selector = float(ratio_entry.get())
    except:
        ratio_ylim_selector = 1
        ratio_entry.delete(0, tk.END)
        ratio_entry.insert(0, "1")
        
update_gui()
root.mainloop()
